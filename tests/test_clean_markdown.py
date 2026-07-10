"""Tests for clean Markdown output: sup/sub -> ^ ~ (not raw HTML), and a visible
placeholder for equations stored as <graphic> images (no MathML/TeX in the XML)."""

from jats.parser import parse_jats_xml
from jats.converter import convert_to_markdown


SUP_XML = """<?xml version="1.0"?>
<article>
  <front><article-meta>
    <title-group><article-title>Sup Test</article-title></title-group>
    <contrib-group>
      <aff id="a1"><institution>Inst One</institution></aff>
      <contrib contrib-type="author"><name><surname>Moore</surname><given-names>Marc</given-names></name>
        <xref ref-type="aff" rid="a1">1</xref></contrib>
    </contrib-group>
  </article-meta></front>
  <body>
    <sec><title>Results</title>
      <p>The value was 5×10<sup>6</sup> cells/ml and CO<sub>2</sub> was controlled.</p>
    </sec>
  </body>
</article>
"""

GRAPHIC_EQ_XML = """<?xml version="1.0"?>
<article xmlns:hwp="http://schema.highwire.org/Journal">
  <front><article-meta>
    <title-group><article-title>Eq Test</article-title></title-group>
  </article-meta></front>
  <body>
    <sec><title>Model</title>
      <p>The dynamics are described by the following equation:</p>
      <disp-formula id="e1"><graphic xlink:href="p1_eqn1.gif" hwp:id="graphic-4"
        xmlns:xlink="http://www.w3.org/1999/xlink"/></disp-formula>
    </sec>
  </body>
</article>
"""

NO_GRAPHIC_EQ_XML = """<?xml version="1.0"?>
<article>
  <front><article-meta>
    <title-group><article-title>No Graphic Eq</article-title></title-group>
  </article-meta></front>
  <body><sec><title>Model</title>
    <p>Described by the equation:</p>
    <disp-formula id="e1"/>
  </sec></body>
</article>
"""


def _md(tmp_path, name, xml, image_base=None):
    p = tmp_path / name
    p.write_text(xml, encoding="utf-8")
    return convert_to_markdown(parse_jats_xml(p, image_base=image_base))


def test_sup_sub_become_markdown_not_html(tmp_path):
    md = _md(tmp_path, "sup.xml", SUP_XML)
    assert "<sup>" not in md and "</sup>" not in md
    assert "<sub>" not in md and "</sub>" not in md
    assert "5×10^6^ cells/ml" in md            # body superscript -> ^6^
    assert "CO~2~" in md                        # body subscript -> ~2~
    assert "Marc Moore^1^" in md                # author affiliation marker -> ^1^


def test_graphic_equation_links_bare_filename(tmp_path):
    # No image_base: link the bare filename the XML carries (caller can resolve it).
    md = _md(tmp_path, "eq.xml", GRAPHIC_EQ_XML)
    assert "described by the following equation:" in md   # sentence not left dangling
    assert "![equation image](p1_eqn1.gif)" in md
    assert "<graphic" not in md and "disp-formula" not in md


def test_graphic_equation_links_absolute_url_with_image_base(tmp_path):
    # With image_base: build <base>/embed/<hwp:id>.gif (bioRxiv asset URL).
    base = "https://ex.org/early/2026/01/01/paper1"
    md = _md(tmp_path, "eq.xml", GRAPHIC_EQ_XML, image_base=base)
    assert "![equation image](https://ex.org/early/2026/01/01/paper1/embed/graphic-4.gif)" in md


def test_graphic_only_equation_without_graphic_falls_back_to_placeholder(tmp_path):
    # An image-less empty disp-formula still must not dangle: placeholder kept.
    md = _md(tmp_path, "noeq.xml", NO_GRAPHIC_EQ_XML)
    assert "equation: image in source, not transcribable from XML" in md


ARTIFACT_XML = """<?xml version="1.0"?>
<article>
  <front><article-meta>
    <title-group><article-title>Box Test</article-title></title-group>
  </article-meta></front>
  <body><sec><title>Stats</title>
    <p>Data are mean□±□s.e.m. Significance: *P□&lt;□0.05.</p>
  </sec></body>
</article>
"""


def test_artifact_box_glyphs_become_spaces(tmp_path):
    # U+25A1 WHITE SQUARE used as a spacing glyph in publisher XML -> normal space.
    md = _md(tmp_path, "box.xml", ARTIFACT_XML)
    assert "□" not in md                      # no box glyphs leak
    assert "mean ± s.e.m." in md                   # spacing restored
    assert "*P < 0.05." in md
