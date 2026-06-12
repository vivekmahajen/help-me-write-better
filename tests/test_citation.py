import io
import json

import pytest

from write_better import citation
from write_better.platform import accounts
from write_better.platform.gateway import make_gateway
from write_better.platform.store import Store


# --- input classification -----------------------------------------------------

def test_classify():
    assert citation.classify("10.1038/nature14539") == "doi"
    assert citation.classify("https://doi.org/10.1038/nature14539") == "doi"
    assert citation.classify("https://example.com/post") == "url"
    assert citation.classify("978-0-13-468599-1") == "isbn"
    assert citation.classify("9780134685991") == "isbn"
    assert citation.classify("Smith, J. (2020). A paper.") == "freetext"


# --- fake HTTP ----------------------------------------------------------------

_CROSSREF = {"message": {
    "type": "journal-article", "title": ["Deep learning"],
    "author": [{"family": "LeCun", "given": "Yann"},
               {"family": "Bengio", "given": "Yoshua"},
               {"family": "Hinton", "given": "Geoffrey"}],
    "container-title": ["Nature"], "issued": {"date-parts": [[2015, 5, 27]]},
    "volume": "521", "issue": "7553", "page": "436-444", "DOI": "10.1038/nature14539",
    "URL": "https://doi.org/10.1038/nature14539"}}

_HTML = ('<html><head><title>Fallback</title>'
         '<meta name="citation_title" content="A Great Post">'
         '<meta name="citation_author" content="Jane Doe">'
         '<meta property="og:site_name" content="Example Blog">'
         '<meta name="citation_publication_date" content="2021-03-04">'
         '</head></html>')

_ISBN = {"title": "The C Programming Language", "publishers": ["Prentice Hall"],
         "publish_date": "1988", "authors": [{"key": "/authors/OL1A"}]}
_AUTHOR = {"name": "Brian Kernighan"}


def fake_http(url, headers):
    if "crossref.org" in url:
        return json.dumps(_CROSSREF)
    if url.endswith("/authors/OL1A.json"):
        return json.dumps(_AUTHOR)
    if "openlibrary.org/isbn" in url:
        return json.dumps(_ISBN)
    return _HTML  # any URL


# --- resolvers + formatting ---------------------------------------------------

APA_FIXTURE = ("LeCun, Y., Bengio, Y., Hinton, G. (2015). Deep learning. *Nature*, "
               "521(7553), 436-444. https://doi.org/10.1038/nature14539")


def test_doi_renders_byte_identical_apa():
    csl, resolver, warnings = citation.resolve("10.1038/nature14539", fake_http)
    assert resolver == "crossref" and warnings == []
    assert citation.format_bibliography(csl, "apa") == APA_FIXTURE


def test_in_text_per_style():
    csl, _, _ = citation.resolve("10.1038/nature14539", fake_http)
    assert citation.format_in_text(csl, "apa") == "(LeCun, 2015)"
    assert citation.format_in_text(csl, "chicago") == "(LeCun 2015)"
    assert citation.format_in_text(csl, "mla") == "(LeCun 436)"


def test_url_extracts_meta_tags():
    csl, resolver, _ = citation.resolve("https://example.com/post", fake_http)
    assert resolver == "url"
    assert csl["title"] == "A Great Post"
    assert csl["container-title"] == "Example Blog"
    assert csl["author"][0]["family"] == "Doe"
    assert csl["author"][0]["given"] == "Jane"
    assert csl["issued"] == 2021


def test_isbn_resolves_author_name():
    csl, resolver, _ = citation.resolve("978-0-13-468599-1", fake_http)
    assert resolver == "openlibrary"
    assert csl["title"] == "The C Programming Language"
    assert csl["author"][0]["family"] == "Kernighan"  # "Brian Kernighan"
    assert csl["author"][0]["given"] == "Brian"


def test_freetext_flagged():
    csl, resolver, warnings = citation.resolve("Smith (2020). A paper.", fake_http)
    assert resolver == "heuristic"
    assert csl["issued"] == 2020
    assert "verify" in warnings[0].lower()


def test_freetext_with_llm_parser():
    def llm(text):
        return {"title": "Parsed Title", "author": [{"family": "AI", "given": ""}]}
    csl, resolver, warnings = citation.resolve("messy ref", fake_http, llm_parse=llm)
    assert resolver == "llm" and csl["title"] == "Parsed Title"


def test_batch_one_bad_input_does_not_fail_others():
    def http(url, headers):
        if "crossref" in url:
            raise RuntimeError("503")  # DOI lookup fails
        return _HTML
    result = citation.cite_batch(
        ["10.1038/nature14539", "https://example.com/post"], "apa", http)
    assert len(result["items"]) == 2
    assert result["items"][0]["warnings"]          # the failed DOI has a warning
    assert "A Great Post" in result["items"][1]["bibliography_entry"]
    assert result["bibliography"] == sorted(result["bibliography"], key=str.lower)


# --- gateway ------------------------------------------------------------------

def _call(app, method, path, token, body=None):
    environ = {"REQUEST_METHOD": method, "PATH_INFO": path, "QUERY_STRING": "",
               "HTTP_AUTHORIZATION": f"Bearer {token}"}
    if body is not None:
        raw = json.dumps(body).encode()
        environ["CONTENT_LENGTH"] = str(len(raw))
        environ["wsgi.input"] = io.BytesIO(raw)
    cap = {}
    out = app(environ, lambda s, h: cap.update(status=s))
    return cap["status"], json.loads(b"".join(out) or b"{}")


@pytest.fixture
def app_token():
    store = Store(":memory:")
    user = accounts.create_user(store, "a@b.com", "supersecret")
    token, _ = accounts.create_api_key(store, user["id"])
    app = make_gateway(store, citation_http=fake_http)
    return app, token, store


def test_gateway_cite_and_save(app_token):
    app, token, store = app_token
    status, data = _call(app, "POST", "/v1/cite", token,
                         {"cite": {"inputs": ["10.1038/nature14539"], "style": "apa",
                                   "save": True}})
    assert status.startswith("200")
    assert data["items"][0]["bibliography_entry"] == APA_FIXTURE
    assert data["items"][0]["in_text"] == "(LeCun, 2015)"

    status, saved = _call(app, "GET", "/v1/citations", token)
    assert status.startswith("200")
    assert len(saved["citations"]) == 1
    assert saved["citations"][0]["csl_json"]["title"] == "Deep learning"


def test_gateway_cite_requires_inputs(app_token):
    app, token, _ = app_token
    status, _ = _call(app, "POST", "/v1/cite", token, {"cite": {"inputs": []}})
    assert status.startswith("400")
