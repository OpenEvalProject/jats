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
<article>
  <front><article-meta>
    <title-group><article-title>Eq Test</article-title></title-group>
  </article-meta></front>
  <body>
    <sec><title>Model</title>
      <p>The dynamics are described by the following equation:</p>
      <disp-formula id="e1"><graphic xlink:href="eq1.gif"
        xmlns:xlink="http://www.w3.org/1999/xlink"/></disp-formula>
    </sec>
  </body>
</article>
"""


def _md(tmp_path, name, xml):
    p = tmp_path / name
    p.write_text(xml, encoding="utf-8")
    return convert_to_markdown(parse_jats_xml(p))


def test_sup_sub_become_markdown_not_html(tmp_path):
    md = _md(tmp_path, "sup.xml", SUP_XML)
    assert "<sup>" not in md and "</sup>" not in md
    assert "<sub>" not in md and "</sub>" not in md
    assert "5×10^6^ cells/ml" in md            # body superscript -> ^6^
    assert "CO~2~" in md                        # body subscript -> ~2~
    assert "Marc Moore^1^" in md                # author affiliation marker -> ^1^


def test_graphic_equation_gets_placeholder(tmp_path):
    md = _md(tmp_path, "eq.xml", GRAPHIC_EQ_XML)
    # the sentence must not dangle with nothing after it
    assert "described by the following equation:" in md
    assert "equation: image in source, not transcribable from XML" in md
    # and no raw <graphic>/<disp-formula> leaks
    assert "<graphic" not in md and "disp-formula" not in md
