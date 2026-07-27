import json
import subprocess
import sys

from jats.bundle import (
    CITATION_CONTEXT_RULE,
    CITATION_SCHEMA_VERSION,
    LITERAL_DOI_RULE,
    STRUCTURED_DOI_RULE,
    build_citation_occurrences,
)

from .test_bundle import SAMPLE


def test_citation_occurrences_preserve_exact_marker_context_and_targets(tmp_path):
    xml_path = tmp_path / "paper.xml"
    xml_path.write_text(SAMPLE)

    bundle = build_citation_occurrences(xml_path)

    assert bundle["schema_version"] == CITATION_SCHEMA_VERSION
    assert bundle["citing_work"]["doi"] == "10.1101/2026.01.02.123456"
    segments = {segment["id"]: segment for segment in bundle["segments"]}
    references = {reference["id"]: reference for reference in bundle["references"]}
    body = next(
        occurrence
        for occurrence in bundle["occurrences"]
        if occurrence["marker"]["text"] == "[1,2]"
    )
    segment_text = segments[body["segment"]]["text"]

    assert body["reference_ids"] == ["R1", "R2"]
    assert segment_text[body["marker"]["start"] : body["marker"]["end"]] == "[1,2]"
    assert (
        segment_text[body["context"]["start"] : body["context"]["end"]]
        == body["context"]["text"]
        == "The measured value increased by 20% [1,2]."
    )
    assert body["context"]["rule"] == CITATION_CONTEXT_RULE
    assert body["id"].startswith("citation_occurrence:sha256:")
    assert body["marker"]["id"].startswith("span:sha256:")
    assert body["context"]["id"].startswith("span:sha256:")
    assert references["R1"]["doi"] == "10.1000/resolved"
    assert references["R1"]["doi_resolution_rule"] == STRUCTURED_DOI_RULE
    assert references["R2"]["doi"] is None
    assert references["R2"]["doi_resolution_rule"] is None


def test_literal_doi_resolution_is_exact_and_ambiguity_preserving(tmp_path):
    xml_path = tmp_path / "paper.xml"
    xml_path.write_text(
        """<article>
  <front><article-meta>
    <article-id pub-id-type="doi">10.1101/example</article-id>
    <title-group><article-title>DOI resolution</article-title></title-group>
  </article-meta></front>
  <body><p>Prior findings support this result <xref ref-type="bibr" rid="R1">1</xref>,
  while two reports disagree <xref ref-type="bibr" rid="R2">2</xref>.</p></body>
  <back><ref-list>
    <ref id="R1"><mixed-citation>One work. https://doi.org/10.5555/Alpha.</mixed-citation></ref>
    <ref id="R2"><mixed-citation>Two works. 10.5555/beta and 10.5555/gamma.</mixed-citation></ref>
  </ref-list></back>
</article>"""
    )

    references = {
        reference["id"]: reference
        for reference in build_citation_occurrences(xml_path)["references"]
    }

    assert references["R1"]["doi"] == "10.5555/alpha"
    assert references["R1"]["doi_resolution_rule"] == LITERAL_DOI_RULE
    assert references["R2"]["doi"] is None
    assert references["R2"]["doi_resolution_rule"] is None


def test_citation_occurrences_are_deterministic(tmp_path):
    xml_path = tmp_path / "paper.xml"
    xml_path.write_text(SAMPLE)
    assert build_citation_occurrences(xml_path) == build_citation_occurrences(xml_path)


def test_citations_cli_matches_the_library(tmp_path):
    xml_path = tmp_path / "paper.xml"
    output_path = tmp_path / "citations.json"
    xml_path.write_text(SAMPLE)

    subprocess.run(
        [
            sys.executable,
            "-m",
            "jats.main",
            "citations",
            str(xml_path),
            "--output",
            str(output_path),
        ],
        check=True,
    )

    assert json.loads(output_path.read_text()) == build_citation_occurrences(xml_path)
