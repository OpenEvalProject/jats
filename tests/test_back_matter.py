"""Tests for <back> matter parsing: Methods/legends sections + reference list."""

from pathlib import Path

from jats.parser import parse_jats_xml
from jats.converter import convert_to_markdown


BACK_XML = """<?xml version="1.0"?>
<article>
  <front><article-meta>
    <title-group><article-title>Test Article</article-title></title-group>
    <abstract><p>An abstract.</p></abstract>
  </article-meta></front>
  <body>
    <sec><title>Introduction</title><p>Body intro paragraph with content here.</p></sec>
  </body>
  <back>
    <sec><title>Methods</title>
      <p>We did the experiment carefully and reproducibly in triplicate.</p>
      <sec><title>Library design</title><p>Oligos were synthesized as described.</p></sec>
    </sec>
    <ack><title>Acknowledgements</title><p>We thank the funders and the lab.</p></ack>
    <ref-list>
      <ref id="c1"><label>1.</label><element-citation>
        <string-name>Smith, J.</string-name><article-title>A great paper</article-title>
        <source>Nature</source><year>2020</year>
        <pub-id pub-id-type="doi">10.1000/xyz1</pub-id>
      </element-citation></ref>
      <ref id="c2"><label>2.</label><element-citation>
        <string-name>Doe, A.</string-name><article-title>Another paper</article-title>
        <source>Cell</source><year>2021</year>
      </element-citation></ref>
    </ref-list>
  </back>
</article>
"""

NO_BACK_XML = """<?xml version="1.0"?>
<article>
  <front><article-meta>
    <title-group><article-title>No Back Article</article-title></title-group>
  </article-meta></front>
  <body><sec><title>Results</title><p>Only a body here.</p></sec></body>
</article>
"""


def _write(tmp_path, name, content):
    p = tmp_path / name
    p.write_text(content, encoding="utf-8")
    return p


def test_back_sections_and_bibliography_parsed(tmp_path):
    xml = _write(tmp_path, "back.xml", BACK_XML)
    article = parse_jats_xml(xml)

    # <back> sections captured
    titles = [s.title for s in article.back]
    assert "Methods" in titles
    assert "Library design" in titles          # nested sec too
    assert any((t or "").startswith("Acknowledge") for t in titles)

    # bibliography captured from <ref-list>
    assert len(article.bibliography) == 2
    assert article.bibliography[0].label == "1."
    assert "great paper" in article.bibliography[0].text
    assert article.bibliography[0].doi == "10.1000/xyz1"

    # Article.references (inline-citation DOI map) still works and is separate
    assert isinstance(article.references, dict)


def test_back_rendered_in_markdown(tmp_path):
    xml = _write(tmp_path, "back.xml", BACK_XML)
    md = convert_to_markdown(parse_jats_xml(xml))

    assert "## Methods" in md
    assert "experiment carefully" in md
    assert "### Library design" in md
    assert "## References" in md
    assert "A great paper" in md
    assert "https://doi.org/10.1000/xyz1" in md   # DOI link present by default


def test_no_back_flag_excludes_back(tmp_path):
    xml = _write(tmp_path, "back.xml", BACK_XML)
    full = convert_to_markdown(parse_jats_xml(xml))
    body_only = convert_to_markdown(parse_jats_xml(xml, no_back=True))

    assert "## Methods" in full and "## Methods" not in body_only
    assert "## References" not in body_only
    assert "Body intro paragraph" in body_only    # body still present


def test_no_refs_strips_doi_links(tmp_path):
    xml = _write(tmp_path, "back.xml", BACK_XML)
    md = convert_to_markdown(parse_jats_xml(xml, no_refs=True), no_refs=True)
    assert "## References" in md                   # list still there
    assert "A great paper" in md                   # citation text kept
    assert "https://doi.org/" not in md            # but DOI link stripped


def test_article_without_back_still_converts(tmp_path):
    xml = _write(tmp_path, "noback.xml", NO_BACK_XML)
    article = parse_jats_xml(xml)
    md = convert_to_markdown(article)

    assert article.back == []
    assert article.bibliography == []
    assert "## References" not in md               # no empty References section
    assert "Only a body here" in md
