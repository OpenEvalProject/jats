"""Tests: non-JATS input fails with a clear ValueError, not a cryptic lxml crash.

Regression for the real-world case where a bioRxiv `.source.xml` URL returns a
"Page Not Found" HTML page (with an unescaped & in an analytics <script>) on 404 or
rate-limit — which previously raised `XMLSyntaxError: EntityRef: expecting ';'`.
"""

import pytest

from jats.parser import parse_jats_xml


HTML_404 = """<!DOCTYPE html>
<html lang="en"><head><title>Page Not Found | bioRxiv</title>
<script type="text/javascript">var dl=l!='dataLayer'?'&l='+l:'';</script>
</head><body><h1>404</h1></body></html>"""

NON_JATS_XML = "<collection><item>not an article</item></collection>"


def test_html_page_raises_valueerror(tmp_path):
    p = tmp_path / "notfound.xml"
    p.write_text(HTML_404, encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        parse_jats_xml(p)
    assert "HTML page" in str(exc.value)


def test_wellformed_non_jats_raises_valueerror(tmp_path):
    p = tmp_path / "other.xml"
    p.write_text(NON_JATS_XML, encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        parse_jats_xml(p)
    assert "JATS" in str(exc.value)
