"""CSL-subset renderer: 5 styles x 4 item types, BibTeX, honest degradation."""

from write_better import citation as c

SAMPLES = {
    "article": {"type": "article-journal", "title": "Deep learning",
        "author": [{"family": "LeCun", "given": "Yann"},
                   {"family": "Bengio", "given": "Yoshua"},
                   {"family": "Hinton", "given": "Geoffrey"}],
        "container-title": "Nature", "issued": 2015, "volume": "521",
        "issue": "7553", "page": "436-444", "DOI": "10.1038/nature14539"},
    "book": {"type": "book", "title": "The C Programming Language",
        "author": [{"family": "Kernighan", "given": "Brian"},
                   {"family": "Ritchie", "given": "Dennis"}],
        "publisher": "Prentice Hall", "issued": 1988},
    "chapter": {"type": "chapter", "title": "Attention Is All You Need",
        "author": [{"family": "Vaswani", "given": "Ashish"}],
        "container-title": "Advances in NIPS", "publisher": "Curran",
        "issued": 2017, "page": "5998-6008"},
    "webpage": {"type": "webpage", "title": "A Great Post",
        "author": [{"family": "Doe", "given": "Jane"}],
        "container-title": "Example Blog", "issued": 2021,
        "URL": "https://example.com/post"},
}

# Golden, hand-reviewed renderings — 5 styles x 4 item types.
GOLDEN = {
    "apa": {
        "article": "LeCun, Y., Bengio, Y., Hinton, G. (2015). Deep learning. *Nature*, 521(7553), 436-444. https://doi.org/10.1038/nature14539",
        "book": "Kernighan, B., Ritchie, D. (1988). *The C Programming Language*. Prentice Hall.",
        "chapter": "Vaswani, A. (2017). Attention Is All You Need. In *Advances in NIPS* (pp. 5998-6008). Curran.",
        "webpage": "Doe, J. (2021). *A Great Post*. Example Blog. https://example.com/post",
    },
    "mla": {
        "article": 'LeCun, Yann, et al. "Deep learning." *Nature*, vol. 521, no. 7553, 2015, pp. 436-444.',
        "book": "Kernighan, Brian, et al. *The C Programming Language*. Prentice Hall, 1988.",
        "chapter": 'Vaswani, Ashish. "Attention Is All You Need." *Advances in NIPS*, Curran, 2017, pp. 5998-6008.',
        "webpage": 'Doe, Jane. "A Great Post." *Example Blog*, 2021, https://example.com/post.',
    },
    "chicago": {
        "article": 'LeCun, Y., Bengio, Y., Hinton, G. 2015. "Deep learning." *Nature* 521 (7553): 436-444.',
        "book": "Kernighan, B., Ritchie, D. 1988. *The C Programming Language*. Prentice Hall.",
        "chapter": 'Vaswani, A. 2017. "Attention Is All You Need." In *Advances in NIPS*, 5998-6008. Curran.',
        "webpage": 'Doe, J. 2021. "A Great Post." *Example Blog*. https://example.com/post.',
    },
    "harvard": {
        "article": "LeCun, Y., Bengio, Y. and Hinton, G. (2015) 'Deep learning', *Nature*, 521(7553), pp. 436-444.",
        "book": "Kernighan, B. and Ritchie, D. (1988) *The C Programming Language*. Prentice Hall.",
        "chapter": "Vaswani, A. (2017) 'Attention Is All You Need', in *Advances in NIPS*. Curran, pp. 5998-6008.",
        "webpage": "Doe, J. (2021) *A Great Post*. Available at: https://example.com/post.",
    },
    "ieee": {
        "article": 'Y. LeCun, Y. Bengio, and G. Hinton, "Deep learning," *Nature*, vol. 521, no. 7553, pp. 436-444, 2015.',
        "book": "B. Kernighan and D. Ritchie, *The C Programming Language*. Prentice Hall, 1988.",
        "chapter": 'A. Vaswani, "Attention Is All You Need," in *Advances in NIPS*. Curran, 2017, pp. 5998-6008.',
        "webpage": 'J. Doe, "A Great Post." [Online]. Available: https://example.com/post',
    },
}


def test_five_styles_four_types_render_byte_identical():
    assert set(GOLDEN) <= set(c.STYLES)
    for style, by_type in GOLDEN.items():
        for item_type, expected in by_type.items():
            got = c.format_bibliography(SAMPLES[item_type], style)
            assert got == expected, f"{style}/{item_type}:\n  got: {got}\n  exp: {expected}"


def test_bibtex_export():
    bib = c.to_bibtex(SAMPLES["article"])
    assert bib.startswith("@article{LeCun2015,")
    assert "author = {LeCun, Yann and Bengio, Yoshua and Hinton, Geoffrey}" in bib
    assert "pages = {436--444}" in bib          # en-dash range for BibTeX
    assert "doi = {10.1038/nature14539}" in bib
    assert c.to_bibtex(SAMPLES["chapter"]).startswith("@incollection{")
    assert c.to_bibtex(SAMPLES["webpage"]).startswith("@misc{")


def test_unknown_style_degrades_with_warning():
    res = c.cite_batch(["10.1038/x"], "vancouver",
                       http=lambda u, h: '{"message":{"title":["T"],"author":[]}}')
    assert res["style"] == "apa"
    assert any("vancouver" in w and "not bundled" in w for w in res["warnings"])


def test_ieee_in_text_is_numbered_by_position():
    def http(u, h):
        return '{"message":{"title":["T"],"author":[{"family":"X","given":"Y"}]}}'
    res = c.cite_batch(["10.1/a", "10.1/b"], "ieee", http,
                       output=("bibliography", "in_text", "bibtex"))
    assert res["items"][0]["in_text"] == "[1]"
    assert res["items"][1]["in_text"] == "[2]"
    assert res["items"][0]["bibtex"].startswith("@")
    assert res["bibtex"].count("@") == 2          # combined export
