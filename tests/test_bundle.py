import hashlib
import json
import subprocess
import sys

from jats.bundle import SCHEMA_VERSION, build_document_bundle

SAMPLE = """<?xml version="1.0" encoding="UTF-8"?>
<article>
  <front>
    <article-meta>
      <article-id pub-id-type="doi">10.1101/2026.01.02.123456</article-id>
      <title-group><article-title>Mapped <italic>science</italic></article-title></title-group>
      <contrib-group>
        <contrib contrib-type="author" corresp="yes">
          <name><surname>Example</surname><given-names>Ada</given-names></name>
          <contrib-id contrib-id-type="orcid">https://orcid.org/0000-0001-2345-6789</contrib-id>
          <xref ref-type="aff" rid="aff1 aff2"/>
        </contrib>
        <aff id="aff1">Department of Examples, Example University</aff>
        <aff id="aff2">Institute of Tests</aff>
      </contrib-group>
      <abstract><p id="abs1">Background evidence cites <xref ref-type="bibr" rid="R1">Smith 2020</xref>.</p></abstract>
    </article-meta>
  </front>
  <body>
    <sec id="sec1">
      <title>Results</title>
      <p id="p1">The measured value increased by 20% <xref ref-type="bibr" rid="R1 R2">[1,2]</xref>.</p>
      <fig id="fig1"><caption><p>Observed values across conditions.</p></caption></fig>
      <table-wrap id="table1">
        <caption><p>Measured values.</p></caption>
        <table><tbody><tr><td>A</td><td>20</td></tr></tbody></table>
      </table-wrap>
    </sec>
  </body>
  <back>
    <ref-list>
      <ref id="R1"><label>1</label><element-citation><article-title>Resolved work</article-title><year>2020</year><pub-id pub-id-type="doi">10.1000/resolved</pub-id></element-citation></ref>
      <ref id="R2"><label>2</label><mixed-citation>Unresolved work. 2019.</mixed-citation></ref>
    </ref-list>
  </back>
</article>
"""


def test_bundle_preserves_grounding_and_citation_identity(tmp_path):
    xml_path = tmp_path / "paper.xml"
    xml_path.write_text(SAMPLE)

    markdown, bundle = build_document_bundle(xml_path)

    assert bundle["schema_version"] == SCHEMA_VERSION
    assert bundle["source"]["sha256"] == hashlib.sha256(SAMPLE.encode()).hexdigest()
    assert bundle["markdown"]["sha256"] == hashlib.sha256(markdown.encode()).hexdigest()
    assert bundle["metadata"]["authors"][0]["affiliation_ids"] == ["aff1", "aff2"]
    assert {reference["id"] for reference in bundle["references"]} == {"R1", "R2"}
    assert (
        next(
            reference for reference in bundle["references"] if reference["id"] == "R1"
        )["doi"]
        == "10.1000/resolved"
    )
    assert (
        next(
            reference for reference in bundle["references"] if reference["id"] == "R2"
        )["doi"]
        == ""
    )

    for segment in bundle["segments"]:
        assert (
            markdown[segment["markdown_start"] : segment["markdown_end"]]
            == segment["text"]
        )

    body_citation = next(
        citation for citation in bundle["citations"] if citation["marker"] == "[1,2]"
    )
    assert body_citation["reference_ids"] == ["R1", "R2"]
    assert body_citation["dois"] == ["10.1000/resolved"]
    segment = next(
        value for value in bundle["segments"] if value["id"] == body_citation["segment"]
    )
    assert segment["text"][body_citation["start"] : body_citation["end"]] == "[1,2]"


def test_bundle_is_deterministic(tmp_path):
    xml_path = tmp_path / "paper.xml"
    xml_path.write_text(SAMPLE)
    assert build_document_bundle(xml_path) == build_document_bundle(xml_path)


def test_bundle_cli_writes_both_artifacts(tmp_path):
    xml_path = tmp_path / "paper.xml"
    markdown_path = tmp_path / "paper.md"
    map_path = tmp_path / "paper.json"
    xml_path.write_text(SAMPLE)

    subprocess.run(
        [
            sys.executable,
            "-m",
            "jats.main",
            "bundle",
            str(xml_path),
            "--markdown",
            str(markdown_path),
            "--output",
            str(map_path),
        ],
        check=True,
    )

    bundle = json.loads(map_path.read_text())
    assert markdown_path.is_file()
    assert bundle["schema_version"] == SCHEMA_VERSION
