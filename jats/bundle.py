"""Deterministic, agent-facing document bundles for JATS articles."""

from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable, Optional

from lxml import etree

SCHEMA_VERSION = "jats.document-bundle.v1"
CITATION_SCHEMA_VERSION = "jats.citation-occurrences.v1"
CITATION_CONTEXT_RULE = "jats:sentence-around-xref:v1"
STRUCTURED_DOI_RULE = "jats:reference-pub-id-doi:v1"
LITERAL_DOI_RULE = "jats:reference-text-doi-exact:v1"

_DOI_PATTERN = re.compile(r"10\.\d{4,9}/[-._;()/:A-Z0-9]+", re.IGNORECASE)


@dataclass
class _Segment:
    kind: str
    element: etree._Element
    text: str
    heading_level: Optional[int] = None


def _local_name(element: etree._Element) -> str:
    return etree.QName(element).localname


def _normalize_text(value: str) -> str:
    return re.sub(r"\s+", " ", value).strip()


def _normalize_doi(value: str) -> str:
    normalized = value.strip().lower()
    for prefix in ("https://doi.org/", "http://doi.org/", "doi:"):
        if normalized.startswith(prefix):
            normalized = normalized[len(prefix) :]
    return normalized.rstrip(".,;:")


def _literal_dois(value: str) -> list[str]:
    dois = {
        normalized
        for match in _DOI_PATTERN.findall(value)
        if (normalized := _normalize_doi(match.rstrip(")]}>")))
    }
    return sorted(dois)


def _content_id(prefix: str, value: dict[str, Any]) -> str:
    encoded = json.dumps(
        value,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    return f"{prefix}:sha256:{hashlib.sha256(encoded).hexdigest()}"


def _element_text(element: etree._Element) -> str:
    return _normalize_text("".join(element.itertext()))


def _first(root: etree._Element, expression: str) -> Optional[etree._Element]:
    values = root.xpath(expression)
    return values[0] if values else None


def _first_text(root: etree._Element, expression: str) -> str:
    element = _first(root, expression)
    return _element_text(element) if element is not None else ""


def _ancestor_names(element: etree._Element) -> set[str]:
    return {_local_name(value) for value in element.iterancestors()}


def _section_level(title: etree._Element) -> int:
    section_count = sum(
        1 for ancestor in title.iterancestors() if _local_name(ancestor) == "sec"
    )
    return min(6, max(2, section_count + 1))


def _body_segments(root: etree._Element) -> list[_Segment]:
    body = _first(root, ".//*[local-name()='body']")
    if body is None:
        return []

    segments: list[_Segment] = []
    for element in body.iter():
        name = _local_name(element)
        ancestors = _ancestor_names(element)

        if name == "title" and _local_name(element.getparent()) == "sec":
            text = _element_text(element)
            if text:
                segments.append(
                    _Segment("section_title", element, text, _section_level(element))
                )
            continue

        if name == "caption":
            parent_name = _local_name(element.getparent())
            if parent_name in {"fig", "table-wrap"}:
                text = _element_text(element)
                if text:
                    kind = "figure_caption" if parent_name == "fig" else "table_caption"
                    segments.append(_Segment(kind, element, text))
            continue

        if name == "p":
            if ancestors & {"caption", "table-wrap", "ref-list", "fn-group"}:
                continue
            text = _element_text(element)
            if text:
                segments.append(_Segment("paragraph", element, text))
            continue

        if name == "tr":
            if "table-wrap" not in ancestors:
                continue
            cells = [
                _element_text(cell)
                for cell in element
                if _local_name(cell) in {"td", "th"} and _element_text(cell)
            ]
            if cells:
                segments.append(_Segment("table_row", element, " | ".join(cells)))
            continue

        if name == "disp-formula":
            text = _element_text(element)
            if text:
                segments.append(_Segment("formula", element, text))

    return segments


def _abstract_segments(root: etree._Element) -> list[_Segment]:
    abstract = _first(root, ".//*[local-name()='abstract']")
    if abstract is None:
        return []

    paragraphs = abstract.xpath(".//*[local-name()='p']")
    if not paragraphs:
        text = _element_text(abstract)
        return [_Segment("abstract", abstract, text)] if text else []

    return [
        _Segment("abstract", paragraph, text)
        for paragraph in paragraphs
        if (text := _element_text(paragraph))
    ]


def _reference_records(
    root: etree._Element, tree: etree._ElementTree
) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    for position, reference in enumerate(
        root.xpath(".//*[local-name()='ref-list']/*[local-name()='ref']"), start=1
    ):
        reference_id = reference.get("id") or f"ref-{position}"
        doi = _first_text(
            reference,
            ".//*[local-name()='pub-id' and "
            "translate(@pub-id-type, 'DOI', 'doi')='doi']",
        )
        title = _first_text(
            reference,
            ".//*[local-name()='article-title' or local-name()='chapter-title']",
        )
        year_text = _first_text(reference, ".//*[local-name()='year']")
        year = int(year_text) if year_text.isdigit() else None
        records.append(
            {
                "id": reference_id,
                "label": _first_text(reference, "./*[local-name()='label']"),
                "title": title,
                "doi": doi,
                "year": year,
                "text": _element_text(reference),
                "xpath": tree.getpath(reference),
            }
        )
    return records


def _authors(root: etree._Element) -> list[dict[str, Any]]:
    records: list[dict[str, Any]] = []
    expression = (
        ".//*[local-name()='contrib-group']/*[local-name()='contrib' "
        "and (not(@contrib-type) or @contrib-type='author')]"
    )
    for position, contribution in enumerate(root.xpath(expression), start=1):
        given = _first_text(contribution, ".//*[local-name()='given-names']")
        surname = _first_text(contribution, ".//*[local-name()='surname']")
        collective = _first_text(contribution, ".//*[local-name()='collab']")
        name = _normalize_text(" ".join(value for value in [given, surname] if value))
        if not name:
            name = collective
        if not name:
            continue
        orcid = _first_text(
            contribution,
            ".//*[local-name()='contrib-id' and @contrib-id-type='orcid']",
        )
        orcid = re.sub(r"^https?://orcid\.org/", "", orcid)
        affiliation_ids = []
        for reference in contribution.xpath(
            ".//*[local-name()='xref' and @ref-type='aff']/@rid"
        ):
            affiliation_ids.extend(str(reference).split())
        records.append(
            {
                "position": position,
                "name": name,
                "given_names": given,
                "surname": surname,
                "orcid": orcid or None,
                "affiliation_ids": affiliation_ids,
                "corresponding": contribution.get("corresp") == "yes",
            }
        )
    return records


def _affiliations(root: etree._Element) -> list[dict[str, str]]:
    values: list[dict[str, str]] = []
    seen: set[str] = set()
    for position, affiliation in enumerate(
        root.xpath(
            ".//*[local-name()='article-meta']/*[local-name()='aff'] | .//*[local-name()='contrib-group']/*[local-name()='aff']"
        ),
        start=1,
    ):
        affiliation_id = affiliation.get("id") or f"aff-{position}"
        if affiliation_id in seen:
            continue
        seen.add(affiliation_id)
        values.append({"id": affiliation_id, "text": _element_text(affiliation)})
    return values


def _render_segment(markdown_parts: list[str], segment: dict[str, Any]) -> None:
    markdown_parts.append(f"<!-- segment:{segment['id']} -->\n")
    prefix = ""
    if segment["kind"] == "title":
        prefix = "# "
    elif segment["kind"] == "section_title":
        prefix = "#" * segment["heading_level"] + " "
    elif segment["kind"] == "reference":
        prefix = f"{segment['reference_number']}. "
    elif segment["kind"] in {"figure_caption", "table_caption"}:
        prefix = "**Caption:** "
    elif segment["kind"] == "formula":
        prefix = "```text\n"

    segment["markdown_start"] = sum(len(part) for part in markdown_parts) + len(prefix)
    markdown_parts.append(prefix)
    markdown_parts.append(segment["text"])
    segment["markdown_end"] = sum(len(part) for part in markdown_parts)
    markdown_parts.append("\n```\n\n" if segment["kind"] == "formula" else "\n\n")


def _citation_records(
    source_segments: Iterable[tuple[dict[str, Any], etree._Element]],
    references: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    reference_by_id = {reference["id"]: reference for reference in references}
    citations: list[dict[str, Any]] = []
    for segment, element in source_segments:
        search_from = 0
        for citation in element.xpath(".//*[local-name()='xref' and @ref-type='bibr']"):
            marker = _element_text(citation)
            if not marker:
                continue
            start = segment["text"].find(marker, search_from)
            if start < 0:
                start = segment["text"].find(marker)
            end = start + len(marker) if start >= 0 else None
            if end is not None:
                search_from = end
            reference_ids = str(citation.get("rid") or "").split()
            dois = [
                reference_by_id[reference_id]["doi"]
                for reference_id in reference_ids
                if reference_id in reference_by_id
                and reference_by_id[reference_id]["doi"]
            ]
            citations.append(
                {
                    "segment": segment["id"],
                    "marker": marker,
                    "start": start if start >= 0 else None,
                    "end": end,
                    "reference_ids": reference_ids,
                    "dois": dois,
                }
            )
    return citations


def _citation_context_span(text: str, start: int, end: int) -> tuple[int, int]:
    """Return deterministic sentence-like boundaries around an inline citation."""
    if start < 0 or end < start or end > len(text):
        raise ValueError("citation marker has invalid segment offsets")

    left = 0
    for index in range(start - 1, -1, -1):
        if _sentence_break_after(text, index):
            left = index + 1
            break

    right = len(text)
    for index in range(end, len(text)):
        if _sentence_break_after(text, index):
            right = index + 1
            break

    while left < right and text[left].isspace():
        left += 1
    while right > left and text[right - 1].isspace():
        right -= 1
    return left, right


def _sentence_break_after(text: str, index: int) -> bool:
    character = text[index]
    if character == "\n":
        return True
    if character not in ".!?":
        return False
    if index + 1 < len(text) and not text[index + 1].isspace():
        return False

    next_index = index + 1
    while next_index < len(text) and text[next_index].isspace():
        next_index += 1
    if next_index == len(text):
        return True
    while next_index < len(text) and text[next_index] in "'\"([{":
        next_index += 1
    if next_index == len(text) or not text[next_index].isupper():
        return False

    prefix = text[:index].rstrip()
    token = prefix.rsplit(maxsplit=1)[-1].lower() if prefix else ""
    abbreviations = {
        "al",
        "approx",
        "dr",
        "e.g",
        "etc",
        "fig",
        "i.e",
        "mr",
        "mrs",
        "prof",
        "ref",
        "vs",
    }
    return token not in abbreviations and not re.fullmatch(r"[a-z]", token)


def _resolved_reference(reference: dict[str, Any]) -> dict[str, Any]:
    structured = _normalize_doi(str(reference.get("doi") or ""))
    rule: Optional[str] = None
    doi: Optional[str] = None
    if structured:
        doi = structured
        rule = STRUCTURED_DOI_RULE
    else:
        candidates = _literal_dois(str(reference.get("text") or ""))
        if len(candidates) == 1:
            doi = candidates[0]
            rule = LITERAL_DOI_RULE
    return {
        "id": reference["id"],
        "label": reference.get("label") or "",
        "title": reference.get("title") or "",
        "year": reference.get("year"),
        "text": reference.get("text") or "",
        "xpath": reference.get("xpath") or "",
        "doi": doi,
        "doi_resolution_rule": rule,
    }


def build_citation_occurrences(xml_path: Path) -> dict[str, Any]:
    """Extract exact inline-citation spans and their JATS bibliography targets."""
    _, bundle = build_document_bundle(xml_path)
    source_sha256 = bundle["source"]["sha256"]
    segment_by_id = {segment["id"]: segment for segment in bundle["segments"]}
    references = [_resolved_reference(reference) for reference in bundle["references"]]
    reference_by_id = {reference["id"]: reference for reference in references}
    cited_segment_ids: set[str] = set()
    occurrences: list[dict[str, Any]] = []

    for citation in bundle["citations"]:
        segment_id = citation["segment"]
        segment = segment_by_id.get(segment_id)
        start = citation.get("start")
        end = citation.get("end")
        if segment is None or not isinstance(start, int) or not isinstance(end, int):
            continue
        text = segment["text"]
        marker = citation["marker"]
        if text[start:end] != marker:
            raise ValueError("citation marker does not match its retained segment")

        context_start, context_end = _citation_context_span(text, start, end)
        reference_ids = [
            reference_id
            for reference_id in citation.get("reference_ids") or []
            if reference_id in reference_by_id
        ]
        identity = {
            "source_sha256": source_sha256,
            "segment": segment_id,
            "start": start,
            "end": end,
            "reference_ids": reference_ids,
        }
        marker_span = {
            "start": start,
            "end": end,
            "text": marker,
        }
        marker_span["id"] = _content_id(
            "span", {**identity, "kind": "citation_marker", **marker_span}
        )
        context_span = {
            "start": context_start,
            "end": context_end,
            "text": text[context_start:context_end],
            "rule": CITATION_CONTEXT_RULE,
        }
        context_span["id"] = _content_id(
            "span", {**identity, "kind": "citation_context", **context_span}
        )
        occurrence = {
            "segment": segment_id,
            "marker": marker_span,
            "context": context_span,
            "reference_ids": reference_ids,
        }
        occurrence["id"] = _content_id("citation_occurrence", identity)
        occurrences.append(occurrence)
        cited_segment_ids.add(segment_id)

    segments = [
        {
            "id": segment["id"],
            "xpath": segment.get("xpath") or "",
            "text": segment["text"],
        }
        for segment in bundle["segments"]
        if segment["id"] in cited_segment_ids
    ]
    return {
        "schema_version": CITATION_SCHEMA_VERSION,
        "source": bundle["source"],
        "citing_work": {
            "doi": _normalize_doi(bundle["metadata"].get("doi") or "") or None,
            "title": bundle["metadata"].get("title") or "",
        },
        "segments": segments,
        "references": references,
        "occurrences": occurrences,
    }


def build_document_bundle(xml_path: Path) -> tuple[str, dict[str, Any]]:
    """Build annotated Markdown and a deterministic source map from JATS XML."""
    source_bytes = xml_path.read_bytes()
    source_sha256 = hashlib.sha256(source_bytes).hexdigest()
    parser = etree.XMLParser(resolve_entities=False, no_network=True)
    tree = etree.parse(str(xml_path), parser)
    root = tree.getroot()

    title_element = _first(root, ".//*[local-name()='article-title']")
    title = _element_text(title_element) if title_element is not None else ""
    source_segments: list[_Segment] = []
    if title_element is not None and title:
        source_segments.append(_Segment("title", title_element, title, 1))
    source_segments.extend(_abstract_segments(root))
    source_segments.extend(_body_segments(root))

    references = _reference_records(root, tree)
    segments: list[dict[str, Any]] = []
    segment_elements: list[tuple[dict[str, Any], etree._Element]] = []
    markdown_parts: list[str] = []
    abstract_heading_written = False

    for position, source_segment in enumerate(source_segments, start=1):
        if source_segment.kind == "abstract" and not abstract_heading_written:
            markdown_parts.append("## Abstract\n\n")
            abstract_heading_written = True
        segment = {
            "id": f"segment-{position:04d}",
            "kind": source_segment.kind,
            "xpath": tree.getpath(source_segment.element),
            "jats_id": source_segment.element.get("id"),
            "text": source_segment.text,
        }
        if source_segment.heading_level is not None:
            segment["heading_level"] = source_segment.heading_level
        _render_segment(markdown_parts, segment)
        segments.append(segment)
        segment_elements.append((segment, source_segment.element))

    if references:
        markdown_parts.append("## References\n\n")
        for number, reference in enumerate(references, start=1):
            segment = {
                "id": f"segment-{len(segments) + 1:04d}",
                "kind": "reference",
                "xpath": reference["xpath"],
                "jats_id": reference["id"],
                "text": reference["text"],
                "reference_number": number,
            }
            _render_segment(markdown_parts, segment)
            segments.append(segment)

    markdown = "".join(markdown_parts).rstrip() + "\n"
    markdown_sha256 = hashlib.sha256(markdown.encode("utf-8")).hexdigest()
    doi = _first_text(
        root,
        ".//*[local-name()='article-id' and "
        "translate(@pub-id-type, 'DOI', 'doi')='doi']",
    )
    bundle = {
        "schema_version": SCHEMA_VERSION,
        "source": {
            "id": f"source:sha256:{source_sha256}",
            "sha256": source_sha256,
            "media_type": "application/xml",
        },
        "markdown": {
            "sha256": markdown_sha256,
            "length": len(markdown),
        },
        "metadata": {
            "doi": doi,
            "title": title,
            "authors": _authors(root),
            "affiliations": _affiliations(root),
        },
        "segments": segments,
        "references": references,
        "citations": _citation_records(segment_elements, references),
    }
    return markdown, bundle
