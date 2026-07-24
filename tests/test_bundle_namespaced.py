from jats.bundle import build_document_bundle


def test_bundle_handles_namespaced_jats_and_front_level_affiliations(tmp_path):
    xml_path = tmp_path / "paper.xml"
    xml_path.write_text(
        """<article xmlns="urn:example:jats">
  <front>
    <article-meta>
      <article-id pub-id-type="doi">10.1101/example</article-id>
      <title-group><article-title>Namespaced article</article-title></title-group>
      <aff id="aff1"><label>1</label> Example University</aff>
      <contrib-group>
        <contrib contrib-type="author">
          <name><surname>Researcher</surname><given-names>Ada</given-names></name>
          <xref ref-type="aff" rid="aff1"/>
        </contrib>
      </contrib-group>
      <abstract><p>One supported statement.</p></abstract>
    </article-meta>
  </front>
  <body><sec><title>Results</title><p>One measured result.</p></sec></body>
</article>"""
    )

    markdown, bundle = build_document_bundle(xml_path)

    assert bundle["metadata"]["doi"] == "10.1101/example"
    assert bundle["metadata"]["affiliations"] == [
        {"id": "aff1", "text": "1 Example University"}
    ]
    assert bundle["metadata"]["authors"][0]["affiliation_ids"] == ["aff1"]
    assert "One measured result." in markdown
