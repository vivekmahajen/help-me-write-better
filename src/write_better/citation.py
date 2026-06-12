"""Citation generation + formatting (Feature 3) — zero marginal cost.

Resolves identifiers to CSL-JSON metadata, then formats per style. No external
key required: DOI → Crossref, ISBN → OpenLibrary, URL → page meta tags,
free-text → an injectable parser (LLM in production; heuristic offline). The HTTP
call is injected (``http(url, headers) -> str``) so tests never hit the network.

Scope note ([VERIFY]): rather than bundle ``citeproc-py`` + the full CSL repo,
this implements focused formatters for the launch styles (APA 7, MLA 9, Chicago
author-date) over the common item types (article-journal, book, webpage). The
CSL-JSON intermediate keeps the door open to swap in a real CSL engine later.
"""

from __future__ import annotations

import json
import re
import urllib.request
from datetime import date
from typing import Callable, Optional

HttpGet = Callable[[str, dict], str]  # (url, headers) -> body text

STYLES = ("apa", "mla", "chicago")
_UA = "help-me-write-better/1.0 (mailto:cite@help-me-write-better.example)"


def default_http(url: str, headers: dict) -> str:  # pragma: no cover - network
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req, timeout=15) as resp:
        return resp.read().decode("utf-8", "replace")


# --- input classification -----------------------------------------------------

def classify(raw: str) -> str:
    s = raw.strip()
    if s.lower().startswith(("http://", "https://")) and "doi.org/" not in s.lower():
        return "url"
    if "doi.org/" in s.lower() or re.match(r"^10\.\d{4,9}/\S+$", s):
        return "doi"
    digits = re.sub(r"[\s-]", "", s)
    if re.match(r"^\d{9}[\dXx]$", digits) or re.match(r"^\d{13}$", digits):
        return "isbn"
    return "freetext"


def _extract_doi(s: str) -> str:
    m = re.search(r"10\.\d{4,9}/\S+", s)
    return m.group(0).rstrip(".,);") if m else s.strip()


# --- resolvers (each returns (csl_json, resolver, warnings)) ------------------

def resolve_doi(raw: str, http: HttpGet) -> tuple[dict, str, list[str]]:
    doi = _extract_doi(raw)
    data = json.loads(http(f"https://api.crossref.org/works/{doi}", {"User-Agent": _UA}))
    m = data.get("message", {})
    csl = {
        "type": {"journal-article": "article-journal", "book": "book"}.get(
            m.get("type", ""), m.get("type", "article-journal")),
        "title": (m.get("title") or [""])[0],
        "author": [{"family": a.get("family", ""), "given": a.get("given", "")}
                   for a in m.get("author", [])],
        "container-title": (m.get("container-title") or [""])[0],
        "issued": _year_from_parts(m.get("issued")),
        "volume": m.get("volume"), "issue": m.get("issue"),
        "page": m.get("page"), "DOI": doi,
        "URL": m.get("URL") or f"https://doi.org/{doi}",
    }
    return csl, "crossref", []


def resolve_isbn(raw: str, http: HttpGet) -> tuple[dict, str, list[str]]:
    isbn = re.sub(r"[\s-]", "", raw)
    data = json.loads(http(f"https://openlibrary.org/isbn/{isbn}.json", {"User-Agent": _UA}))
    warnings = []
    authors = []
    for ref in data.get("authors", []):
        key = ref.get("key")
        try:
            adata = json.loads(http(f"https://openlibrary.org{key}.json", {"User-Agent": _UA}))
            authors.append(_split_name(adata.get("name", "")))
        except Exception:
            warnings.append("author name could not be resolved")
    csl = {
        "type": "book", "title": data.get("title", ""), "author": authors,
        "publisher": (data.get("publishers") or [""])[0],
        "issued": _year_from_date_str(data.get("publish_date")),
        "ISBN": isbn,
    }
    return csl, "openlibrary", warnings


def resolve_url(raw: str, http: HttpGet) -> tuple[dict, str, list[str]]:
    html = http(raw, {"User-Agent": _UA})
    meta = _meta_tags(html)
    title = (meta.get("citation_title") or meta.get("og:title")
             or _html_title(html) or raw)
    site = meta.get("og:site_name") or _hostname(raw)
    authors = [_split_name(a) for a in meta.get("citation_author_list", [])]
    csl = {
        "type": "webpage", "title": title, "author": authors,
        "container-title": site, "URL": raw,
        "issued": _year_from_date_str(meta.get("citation_publication_date")
                                      or meta.get("article:published_time")),
        "accessed": date.today().year,
    }
    warnings = [] if authors else ["no author found; cite by title"]
    return csl, "url", warnings


def resolve_freetext(raw: str, llm_parse: Optional[Callable[[str], Optional[dict]]]
                     ) -> tuple[dict, str, list[str]]:
    if llm_parse:
        parsed = llm_parse(raw)
        if parsed:
            parsed.setdefault("type", "article-journal")
            return parsed, "llm", ["AI-parsed reference — verify all fields."]
    # offline heuristic: "Author, A. (Year). Title. Container."
    csl = {"type": "article-journal", "title": raw.strip(), "author": []}
    m = re.search(r"\((\d{4})\)", raw)
    if m:
        csl["issued"] = int(m.group(1))
    return csl, "heuristic", ["Parsed heuristically — verify all fields."]


def resolve(raw: str, http: HttpGet, llm_parse=None) -> tuple[dict, str, list[str]]:
    kind = classify(raw)
    try:
        if kind == "doi":
            return resolve_doi(raw, http)
        if kind == "isbn":
            return resolve_isbn(raw, http)
        if kind == "url":
            return resolve_url(raw, http)
        return resolve_freetext(raw, llm_parse)
    except Exception as exc:
        return {"type": "document", "title": raw.strip(), "author": []}, kind, \
               [f"could not resolve ({kind}): {exc}"]


# --- formatters ---------------------------------------------------------------

def _names_apa(authors):
    parts = []
    for a in authors:
        initials = " ".join(f"{p[0]}." for p in a.get("given", "").split() if p)
        parts.append(f"{a.get('family','')}, {initials}".strip().rstrip(","))
    return ", ".join(parts)


def _names_mla(authors):
    if not authors:
        return ""
    a = authors[0]
    lead = f"{a.get('family','')}, {a.get('given','')}".strip().rstrip(",")
    return lead + (", et al" if len(authors) > 1 else "")


def _year(csl):
    return csl.get("issued") or "n.d."


def format_bibliography(csl: dict, style: str) -> str:
    style = style.lower()
    title = csl.get("title", "")
    container = csl.get("container-title", "")
    year = _year(csl)
    if style == "apa":
        out = f"{_names_apa(csl.get('author', []))} ({year}). {title}."
        if container:
            vol = csl.get("volume") or ""
            iss = f"({csl['issue']})" if csl.get("issue") else ""
            page = f", {csl['page']}" if csl.get("page") else ""
            out += f" *{container}*"
            out += f", {vol}{iss}{page}." if vol or page else "."
        if csl.get("publisher"):
            out += f" {csl['publisher']}."
        if csl.get("DOI"):
            out += f" https://doi.org/{csl['DOI']}"
        elif csl.get("URL") and csl.get("type") == "webpage":
            out += f" {csl['URL']}"
        return _squish(out)
    if style == "mla":
        names = _names_mla(csl.get("author", []))
        out = f"{names + '. ' if names else ''}\"{title}.\""
        if container:
            out += f" *{container}*,"
        if csl.get("volume"):
            out += f" vol. {csl['volume']},"
        if csl.get("issue"):
            out += f" no. {csl['issue']},"
        out += f" {year}"
        if csl.get("page"):
            out += f", pp. {csl['page']}"
        out += "."
        return _squish(out)
    # chicago author-date
    out = f"{_names_apa(csl.get('author', []))}. {year}. \"{title}.\""
    if container:
        out += f" *{container}*"
        if csl.get("volume"):
            out += f" {csl['volume']}"
        if csl.get("issue"):
            out += f" ({csl['issue']})"
        if csl.get("page"):
            out += f": {csl['page']}"
        out += "."
    if csl.get("publisher"):
        out += f" {csl['publisher']}."
    return _squish(out)


def format_in_text(csl: dict, style: str) -> str:
    style = style.lower()
    authors = csl.get("author", [])
    fam = authors[0]["family"] if authors else (csl.get("title", "")[:20])
    year = _year(csl)
    if style == "mla":
        page = csl.get("page", "").split("-")[0] if csl.get("page") else ""
        return f"({fam}{(' ' + page) if page else ''})"
    if style == "chicago":
        return f"({fam} {year})"
    return f"({fam}, {year})"  # apa


# --- helpers ------------------------------------------------------------------

def _split_name(display: str) -> dict:
    """Parse a display-order name ("First Middle Last") into given/family."""
    parts = display.strip().rsplit(" ", 1)
    if len(parts) == 2 and parts[0]:
        return {"given": parts[0], "family": parts[1]}
    return {"family": display.strip(), "given": ""}


def _year_from_parts(issued):
    try:
        return issued["date-parts"][0][0]
    except (KeyError, IndexError, TypeError):
        return None


def _year_from_date_str(s):
    if not s:
        return None
    m = re.search(r"\d{4}", str(s))
    return int(m.group(0)) if m else None


def _meta_tags(html: str) -> dict:
    meta = {"citation_author_list": []}
    for m in re.finditer(r'<meta[^>]+>', html, re.IGNORECASE):
        tag = m.group(0)
        name = _attr(tag, "name") or _attr(tag, "property")
        content = _attr(tag, "content")
        if not name or content is None:
            continue
        if name.lower() == "citation_author":
            meta["citation_author_list"].append(content)
        else:
            meta[name.lower()] = content
    return meta


def _attr(tag, attr):
    m = re.search(attr + r'\s*=\s*["\']([^"\']*)["\']', tag, re.IGNORECASE)
    return m.group(1) if m else None


def _html_title(html):
    m = re.search(r"<title[^>]*>(.*?)</title>", html, re.IGNORECASE | re.DOTALL)
    return m.group(1).strip() if m else None


def _hostname(url):
    m = re.match(r"https?://([^/]+)", url)
    return m.group(1) if m else url


def _squish(s):
    return re.sub(r"\s+", " ", s).replace(" .", ".").replace(",.", ".").strip()


def cite_batch(inputs: list[str], style: str, http: HttpGet, *,
               output=("bibliography", "in_text"), llm_parse=None) -> dict:
    """Resolve + format each input independently; one bad line is a per-line
    warning, not a failed batch. Returns per-input results + a combined,
    alphabetized bibliography."""
    style = style.lower()
    if style not in STYLES:
        style = "apa"
    items = []
    for raw in inputs:
        csl, resolver, warnings = resolve(raw, http, llm_parse)
        entry = format_bibliography(csl, style)
        item = {"input": raw, "csl_json": csl, "resolver": resolver,
                "warnings": warnings, "parsed_by": resolver}
        if "bibliography" in output:
            item["bibliography_entry"] = entry
        if "in_text" in output:
            item["in_text"] = format_in_text(csl, style)
        items.append(item)
    bib = sorted((it.get("bibliography_entry", "") for it in items), key=str.lower)
    return {"style": style, "items": items, "bibliography": bib}
