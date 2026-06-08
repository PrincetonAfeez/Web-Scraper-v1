"""Unit test for HTML parser."""

from __future__ import annotations

from scrapehound.parse.stdlib_parser import StdlibHTMLParser


def test_stdlib_parser_extracts_metadata_and_resolves_links():
    page = StdlibHTMLParser().parse(
        b"""
        <html>
          <head>
            <base href="http://example.com/base/">
            <title> Test Page </title>
            <meta name="description" content="Example description">
          </head>
          <body>
            <h1>Hello</h1>
            <h2>World</h2>
            <a href="../next">Next</a>
          </body>
        </html>
        """,
        "http://example.com/base/index.html",
        "text/html; charset=utf-8",
    )

    assert page.title == "Test Page"
    assert page.description == "Example description"
    assert page.headings == ["Hello", "World"]
    assert page.links == ["http://example.com/next"]


def test_parser_captures_all_heading_levels_and_navigational_tags():
    page = StdlibHTMLParser().parse(
        b"<html><body><h3>Three</h3><h6>Six</h6>"
        b"<area href='/area'><iframe src='/frame'></iframe>"
        b"<a href='/a'>a</a></body></html>",
        "http://x.com/",
        "text/html",
    )

    assert page.headings == ["Three", "Six"]
    assert page.links == ["http://x.com/area", "http://x.com/frame", "http://x.com/a"]


def test_parser_skips_non_navigational_links_and_dedupes():
    page = StdlibHTMLParser().parse(
        b"<html><body>"
        b"<a href='#frag'>frag</a><a href=''>empty</a>"
        b"<a href='javascript:void(0)'>js</a><a href='mailto:a@b.com'>mail</a>"
        b"<a href='/p#sec'>p</a><a href='/p'>dup</a>"
        b"</body></html>",
        "http://x.com/",
        "text/html",
    )

    assert page.links == ["http://x.com/p"]  # fragment stripped, duplicate dropped


def test_parser_prefers_description_meta_over_og():
    page = StdlibHTMLParser().parse(
        b"<html><head>"
        b"<meta property='og:description' content='og'>"
        b"<meta name='description' content='real'>"
        b"</head><body></body></html>",
        "http://x.com/",
        "text/html",
    )

    assert page.description == "real"


def test_parser_recovers_from_unterminated_title():
    page = StdlibHTMLParser().parse(b"<title>Real Title<meta name=x><body><h1>H</h1>", "http://x.com/", "text/html")

    assert page.title == "Real Title"


def test_closed_title_preserves_encoded_angle_bracket():
    # A properly closed <title> with &lt; must not be truncated.
    page = StdlibHTMLParser().parse(
        b"<html><head><title>A &lt; B</title></head><body></body></html>",
        "http://x.com/",
        "text/html",
    )

    assert page.title == "A < B"
