"""Tests for optional bioRxiv figure image links (--figure-base).

Figures live at <figure_base>/<hwp-id>.large.jpg where hwp-id is the <fig>'s highwire id
(F1, F2, …). Without the flag, behavior is unchanged (bare href the XML carries).
"""

from jats.parser import parse_jats_xml
from jats.converter import convert_to_markdown


FIG_XML = """<?xml version="1.0"?>
<article xmlns:hwp="http://schema.highwire.org/Journal">
  <front><article-meta>
    <title-group><article-title>Fig Test</article-title></title-group>
  </article-meta></front>
  <body><sec><title>Results</title>
    <fig id="fig1" hwp:id="F1">
      <label>Figure 1.</label>
      <caption><p>A nice figure.</p></caption>
      <graphic xlink:href="paper_fig1" hwp:id="graphic-1"
        xmlns:xlink="http://www.w3.org/1999/xlink"/>
    </fig>
  </sec></body>
</article>
"""


def _md(tmp_path, xml, figure_base=None):
    p = tmp_path / "f.xml"
    p.write_text(xml, encoding="utf-8")
    return convert_to_markdown(parse_jats_xml(p, figure_base=figure_base))


def test_default_keeps_bare_href(tmp_path):
    md = _md(tmp_path, FIG_XML)
    assert "![Figure 1.](paper_fig1)" in md          # unchanged behavior


def test_figure_base_builds_large_jpg_url(tmp_path):
    md = _md(tmp_path, FIG_XML, figure_base="https://ex.org/content/early/2026/01/01/p1")
    # uses the <fig> hwp:id (F1), NOT the <graphic> id (graphic-1)
    assert "![Figure 1.](https://ex.org/content/early/2026/01/01/p1/F1.large.jpg)" in md
    assert "graphic-1" not in md
    # caption still rendered
    assert "**Figure 1.:** A nice figure." in md
