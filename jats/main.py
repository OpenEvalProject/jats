"""Main CLI entry point for jats."""

import json
import re
import sys
from argparse import ArgumentParser, Namespace, RawTextHelpFormatter
from pathlib import Path

from . import __version__
from .converter import (
    convert_response_to_markdown,
    convert_review_to_markdown,
    convert_to_markdown,
)
from .parser import (
    parse_jats_xml,
    parse_doi,
    parse_title,
    parse_abstract,
    parse_pub_date,
    parse_authors,
    parse_affiliations_detailed,
)
from lxml import etree


def setup_metadata_args(subparsers) -> ArgumentParser:
    """Setup the metadata command arguments."""
    subparser = subparsers.add_parser(
        "metadata",
        description="Extract manuscript metadata (DOI, title, abstract, pub_date) from JATS XML file.",
        help="Extract manuscript metadata to JSON",
        formatter_class=RawTextHelpFormatter,
    )

    subparser.add_argument("xml", type=Path, help="JATS XML file to process")

    subparser.add_argument(
        "-o",
        "--output",
        metavar="OUT",
        type=Path,
        help="Output JSON file (default: stdout)",
        default=None,
    )

    return subparser


def validate_metadata_args(parser: ArgumentParser, args: Namespace) -> None:
    """Validate metadata command arguments."""
    if not args.xml.exists():
        parser.error(f"Input file does not exist: {args.xml}")

    if not args.xml.suffix.lower() in [".xml", ".jats"]:
        parser.error(f"Input file must be XML: {args.xml}")

    if args.output and args.output.exists() and not args.output.is_file():
        parser.error(f"Output path exists but is not a file: {args.output}")


def run_metadata(parser: ArgumentParser, args: Namespace) -> None:
    """Run the metadata command."""
    validate_metadata_args(parser, args)

    # Parse XML
    tree = etree.parse(str(args.xml))
    root = tree.getroot()

    # Extract basic metadata
    doi = parse_doi(root)
    title = parse_title(root)
    abstract = parse_abstract(root)
    pub_date = parse_pub_date(root)

    # Extract author and affiliation data
    authors, _ = parse_authors(root)  # Returns authors with basic affiliation text
    affiliations_detailed = parse_affiliations_detailed(root)  # Returns structured affiliation data

    # Convert authors to dict format for JSON
    authors_list = []
    for author in authors:
        author_dict = {
            "given_names": author.given_names,
            "surname": author.surname,
            "orcid": author.orcid,
            "affiliation_ids": author.affiliation_ids,
            "corresponding": author.corresponding,
            "position": author.position
        }
        authors_list.append(author_dict)

    # Convert affiliations to list format for JSON
    affiliations_list = []
    for aff_id, aff_data in affiliations_detailed.items():
        aff_dict = {
            "id": aff_id,
            "institution": aff_data.get("institution"),
            "department": aff_data.get("department"),
            "city": aff_data.get("city"),
            "country": aff_data.get("country"),
            "ror": aff_data.get("ror")
        }
        affiliations_list.append(aff_dict)

    # Create metadata dictionary
    metadata = {
        "doi": doi,
        "title": title,
        "abstract": abstract,
        "pub_date": pub_date,
        "authors": authors_list,
        "affiliations": affiliations_list
    }

    # Output JSON
    json_output = json.dumps(metadata, indent=2, ensure_ascii=False)

    if args.output:
        args.output.write_text(json_output, encoding='utf-8')
        print(f"Extracted metadata from {args.xml} -> {args.output}", file=sys.stderr)
    else:
        print(json_output)


def setup_convert_args(subparsers) -> ArgumentParser:
    """Setup the convert command arguments."""
    subparser = subparsers.add_parser(
        "convert",
        description="Convert JATS XML file to Markdown format.",
        help="Convert JATS XML to Markdown",
        formatter_class=RawTextHelpFormatter,
    )

    subparser.add_argument("xml", type=Path, help="JATS XML file to convert")

    subparser.add_argument(
        "-o",
        "--output",
        metavar="OUT",
        type=Path,
        help="Output file (default: stdout)",
        default=None,
    )

    subparser.add_argument(
        "-p",
        "--peer-reviews",
        type=Path,
        help="Output file for peer review comments (extracts sub-articles)",
        default=None,
    )

    subparser.add_argument(
        "-a",
        "--author-response",
        type=Path,
        help="Output file for author responses (extracts sub-articles)",
        default=None,
    )

    subparser.add_argument(
        "-m",
        "--manifest",
        type=Path,
        help="Optional manifest.xml file (bioRxiv)",
        default=None,
    )

    subparser.add_argument(
        "--no-refs",
        action="store_true",
        help="Strip URL links from references (keep only citation text like 'Author, Year')",
        default=False,
    )

    return subparser


def validate_convert_args(parser: ArgumentParser, args: Namespace) -> None:
    """Validate convert command arguments."""
    if not args.xml.exists():
        parser.error(f"Input file does not exist: {args.xml}")

    if not args.xml.suffix.lower() in [".xml", ".jats"]:
        parser.error(f"Input file must be XML: {args.xml}")

    if args.output and args.output.exists() and not args.output.is_file():
        parser.error(f"Output path exists but is not a file: {args.output}")

    if args.peer_reviews and args.peer_reviews.exists() and not args.peer_reviews.is_file():
        parser.error(f"Peer reviews path exists but is not a file: {args.peer_reviews}")

    if args.author_response and args.author_response.exists() and not args.author_response.is_file():
        parser.error(f"Author response path exists but is not a file: {args.author_response}")

    if args.manifest:
        if not args.manifest.exists():
            parser.error(f"Manifest file does not exist: {args.manifest}")


def run_convert(parser: ArgumentParser, args: Namespace) -> None:
    """Run the convert command."""
    validate_convert_args(parser, args)

    # Parse JATS XML
    article = parse_jats_xml(args.xml, manifest_path=args.manifest, no_refs=args.no_refs)

    # Convert to markdown
    markdown = convert_to_markdown(article)

    # Output manuscript
    if args.output:
        args.output.write_text(markdown, encoding='utf-8')
        print(f"Converted {args.xml} -> {args.output}", file=sys.stderr)
    else:
        print(markdown)

    # Handle peer reviews if requested
    if args.peer_reviews or args.author_response:
        if article.sub_articles:
            # Separate decision letters and author responses
            decision_letters = []
            author_responses = []

            for sub_article in article.sub_articles:
                # JATS4R article types for reviews/reports
                if sub_article.article_type in [
                    'decision-letter',
                    'editor-report',
                    'referee-report',
                    'article-commentary',
                ]:
                    decision_letters.append(sub_article)
                # JATS4R article types for author responses
                elif sub_article.article_type in [
                    'reply',
                    'author-comment',
                ]:
                    author_responses.append(sub_article)

            # Output peer reviews if requested
            if args.peer_reviews:
                if decision_letters:
                    review_parts = []
                    for idx, review in enumerate(decision_letters, 1):
                        # Use revision_round if available, otherwise use sequential number
                        round_num = review.revision_round if review.revision_round else 1
                        review_markdown = convert_review_to_markdown(review, round_num)
                        review_parts.append(review_markdown)
                        if idx < len(decision_letters):
                            review_parts.append("\n---\n")

                    args.peer_reviews.write_text('\n'.join(review_parts), encoding='utf-8')
                    print(f"Extracted peer reviews -> {args.peer_reviews}", file=sys.stderr)
                else:
                    print(f"Warning: No peer review content found in {args.xml}", file=sys.stderr)

            # Output author responses if requested
            if args.author_response:
                if author_responses:
                    response_parts = []
                    for idx, response in enumerate(author_responses, 1):
                        # Use revision_round if available, otherwise use sequential number
                        round_num = response.revision_round if response.revision_round else 1
                        response_markdown = convert_response_to_markdown(response, article, round_num)
                        response_parts.append(response_markdown)
                        if idx < len(author_responses):
                            response_parts.append("\n---\n")

                    args.author_response.write_text('\n'.join(response_parts), encoding='utf-8')
                    print(f"Extracted author responses -> {args.author_response}", file=sys.stderr)
                else:
                    print(f"Warning: No author response content found in {args.xml}", file=sys.stderr)
        else:
            if args.peer_reviews or args.author_response:
                print(f"Warning: No sub-articles found in {args.xml}", file=sys.stderr)


def setup_find_args(subparsers) -> ArgumentParser:
    """Setup the find command arguments."""
    subparser = subparsers.add_parser(
        "find",
        description=(
            "Find query strings in JATS XML and return precise XML-anchored locations.\n\n"
            "Examples:\n"
            "  jats find paper.xml --query \"protein expression\"\n"
            "  jats find paper.xml --query \"claim 1\" --query \"claim 2\"\n"
            "  jats find paper.xml --queries queries.txt -o matches.json\n"
            "  jats find paper.xml --query \"Case Sensitive\" --case-sensitive\n"
        ),
        help="Find query strings in JATS XML",
        formatter_class=RawTextHelpFormatter,
    )

    subparser.add_argument("xml", type=Path, help="JATS XML file to search")

    subparser.add_argument(
        "--query",
        action="append",
        dest="queries_list",
        help="Query string to find (may be repeated)",
    )

    subparser.add_argument(
        "--queries",
        type=Path,
        help="Text file with one query per line",
    )

    subparser.add_argument(
        "-o",
        "--output",
        metavar="OUT",
        type=Path,
        help="Output JSON file (default: stdout)",
        default=None,
    )

    subparser.add_argument(
        "--case-sensitive",
        action="store_true",
        help="Perform case-sensitive matching (default: case-insensitive)",
    )

    return subparser


def validate_find_args(parser: ArgumentParser, args: Namespace) -> None:
    """Validate find command arguments."""
    if not args.xml.exists():
        parser.error(f"Input file does not exist: {args.xml}")

    if not args.xml.suffix.lower() in [".xml", ".jats"]:
        parser.error(f"Input file must be XML: {args.xml}")

    # Must have at least one query source
    if not args.queries_list and not args.queries:
        parser.error("Must provide at least one query via --query or --queries")

    # Validate queries file if provided
    if args.queries:
        if not args.queries.exists():
            parser.error(f"Queries file does not exist: {args.queries}")
        if not args.queries.is_file():
            parser.error(f"Queries path is not a file: {args.queries}")

    # Validate output path if provided
    if args.output and args.output.exists() and not args.output.is_file():
        parser.error(f"Output path exists but is not a file: {args.output}")


def run_find(parser: ArgumentParser, args: Namespace) -> None:
    """Run the find command."""
    from .parser import find_text_locations

    validate_find_args(parser, args)

    # Collect queries from both sources
    queries = []

    # Add queries from --query arguments
    if args.queries_list:
        queries.extend(args.queries_list)

    # Add queries from --queries file
    if args.queries:
        try:
            queries_text = args.queries.read_text(encoding='utf-8')
            # Split by lines, strip whitespace, skip empty lines
            file_queries = [
                line.strip()
                for line in queries_text.splitlines()
                if line.strip()
            ]
            queries.extend(file_queries)
        except Exception as e:
            parser.error(f"Error reading queries file: {e}")

    if not queries:
        parser.error("No queries provided (queries file may be empty)")

    # Parse XML
    try:
        tree = etree.parse(str(args.xml))
        root = tree.getroot()
    except Exception as e:
        print(f"Error parsing XML: {e}", file=sys.stderr)
        sys.exit(1)

    # Find text locations
    try:
        results = find_text_locations(root, queries, args.case_sensitive)
    except Exception as e:
        print(f"Error finding text locations: {e}", file=sys.stderr)
        sys.exit(1)

    # Format as JSON
    json_output = json.dumps(results, indent=2, ensure_ascii=False)

    # Output results
    if args.output:
        args.output.write_text(json_output, encoding='utf-8')
        matches_found = sum(1 for r in results if 'start' in r)
        print(
            f"Found {matches_found}/{len(queries)} queries -> {args.output}",
            file=sys.stderr
        )
    else:
        print(json_output)


def setup_text_args(subparsers) -> ArgumentParser:
    """Setup the text command arguments."""
    subparser = subparsers.add_parser(
        "text",
        description=(
            "Extract plain text from JATS XML (matches jats find output).\\n\\n"
            "This command extracts pure text using itertext(), producing output\\n"
            "that is guaranteed to match what 'jats find' searches against.\\n"
            "Use this for claim extraction, validation, and text matching.\\n\\n"
            "Examples:\\n"
            "  jats text paper.xml\\n"
            "  jats text paper.xml -o paper.txt\\n"
            "  jats text paper.xml --section abstract\\n"
        ),
        help="Extract plain text (matches jats find)",
        formatter_class=RawTextHelpFormatter,
    )

    subparser.add_argument("xml", type=Path, help="JATS XML file to extract text from")

    subparser.add_argument(
        "-o",
        "--output",
        metavar="OUT",
        type=Path,
        help="Output text file (default: stdout)",
        default=None,
    )

    subparser.add_argument(
        "--section",
        choices=["all", "abstract", "body"],
        default="all",
        help="Which section to extract (default: all)",
    )

    return subparser


def validate_text_args(parser: ArgumentParser, args: Namespace) -> None:
    """Validate text command arguments."""
    if not args.xml.exists():
        parser.error(f"Input file does not exist: {args.xml}")

    if not args.xml.suffix.lower() in [".xml", ".jats"]:
        parser.error(f"Input file must be XML: {args.xml}")

    if args.output and args.output.exists() and not args.output.is_file():
        parser.error(f"Output path exists but is not a file: {args.output}")


def run_text(parser: ArgumentParser, args: Namespace) -> None:
    """Run the text command."""
    validate_text_args(parser, args)

    # Parse XML
    tree = etree.parse(str(args.xml))
    root = tree.getroot()

    # Extract text based on section
    text_parts = []

    if args.section in ["all", "abstract"]:
        # Extract abstract
        abstract = root.find('.//abstract')
        if abstract is not None:
            # Remove DOI elements before extracting text
            for obj_id in abstract.findall('.//object-id[@pub-id-type="doi"]'):
                parent = obj_id.getparent()
                if parent is not None:
                    parent.remove(obj_id)
            for para in abstract.findall('.//p'):
                bold_elem = para.find('bold')
                if bold_elem is not None and bold_elem.text and 'DOI' in bold_elem.text:
                    parent = para.getparent()
                    if parent is not None:
                        parent.remove(para)

            abstract_text = ' '.join(abstract.itertext()).strip()
            if abstract_text:
                text_parts.append(abstract_text)

    if args.section in ["all", "body"]:
        # Extract body
        body = root.find('.//body')
        if body is not None:
            # Remove DOI elements before extracting text
            for obj_id in body.findall('.//object-id[@pub-id-type="doi"]'):
                parent = obj_id.getparent()
                if parent is not None:
                    parent.remove(obj_id)
            # Remove paragraphs with DOI text
            for para in body.findall('.//p'):
                bold_elem = para.find('bold')
                if bold_elem is not None and bold_elem.text and 'DOI' in bold_elem.text:
                    parent = para.getparent()
                    if parent is not None:
                        parent.remove(para)

            body_text = ' '.join(body.itertext()).strip()
            if body_text:
                text_parts.append(body_text)

    # Join with double newline (paragraph spacing)
    full_text = '\n\n'.join(text_parts)

    # Output
    if args.output:
        args.output.write_text(full_text, encoding='utf-8')
        print(f"Extracted text from {args.xml} -> {args.output}", file=sys.stderr)
    else:
        print(full_text)


def setup_annotate_args(subparsers) -> ArgumentParser:
    """Setup the annotate command arguments."""
    subparser = subparsers.add_parser(
        "annotate",
        description=(
            "Inject <named-content> tags for claims at precise XPath positions.\n\n"
            "This command reads a JATS XML file and a pos_claims.json file with\n"
            "precise XPath and character offset positions, then injects JATS-standard\n"
            "<named-content> tags to mark the claim locations in the XML.\n\n"
            "Examples:\n"
            "  jats annotate paper.xml --claims pos_claims.json -o annotated.xml\n"
        ),
        help="Annotate JATS XML with claim positions",
        formatter_class=RawTextHelpFormatter,
    )

    subparser.add_argument("xml", type=Path, help="JATS XML file to annotate")

    subparser.add_argument(
        "--claims",
        type=Path,
        required=True,
        help="pos_claims.json file with XPath position data",
    )

    subparser.add_argument(
        "-o",
        "--output",
        metavar="OUT",
        type=Path,
        required=True,
        help="Output annotated XML file",
    )

    return subparser


def validate_annotate_args(parser: ArgumentParser, args: Namespace) -> None:
    """Validate annotate command arguments."""
    if not args.xml.exists():
        parser.error(f"Input XML file does not exist: {args.xml}")

    if not args.xml.suffix.lower() in [".xml", ".jats"]:
        parser.error(f"Input file must be XML: {args.xml}")

    if not args.claims.exists():
        parser.error(f"Claims file does not exist: {args.claims}")

    if not args.claims.suffix.lower() == ".json":
        parser.error(f"Claims file must be JSON: {args.claims}")

    if args.output.exists():
        parser.error(f"Output file already exists: {args.output}")


def run_annotate(parser: ArgumentParser, args: Namespace) -> None:
    """Run the annotate command."""
    from .annotate import inject_named_content_tags

    validate_annotate_args(parser, args)

    # Inject named-content tags
    try:
        root, successful, failed = inject_named_content_tags(args.xml, args.claims)
    except Exception as e:
        print(f"Error annotating XML: {e}", file=sys.stderr)
        sys.exit(1)

    # Write output
    try:
        tree = etree.ElementTree(root)
        tree.write(
            str(args.output),
            encoding='utf-8',
            xml_declaration=True,
            pretty_print=True
        )
        print(
            f"Annotated {args.xml} with {successful} claims -> {args.output}",
            file=sys.stderr
        )
        if failed > 0:
            print(f"Warning: {failed} claims failed to annotate", file=sys.stderr)
    except Exception as e:
        print(f"Error writing output: {e}", file=sys.stderr)
        sys.exit(1)


def setup_elife_score_args(subparsers) -> ArgumentParser:
    """Setup the elife-score command arguments."""
    subparser = subparsers.add_parser(
        "elife-score",
        description=(
            "Extract eLife assessment from JATS XML editor-report sub-article.\n\n"
            "This command extracts assessment data from the <sub-article\n"
            "article-type='editor-report'> section including assessment text,\n"
            "editor information, and ratings.\n\n"
            "Examples:\n"
            "  jats elife-score paper.xml -o score.json\n"
            "  jats elife-score paper.xml -o score.json -v\n"
        ),
        help="Extract eLife assessment to JSON",
        formatter_class=RawTextHelpFormatter,
    )

    subparser.add_argument("xml", type=Path, help="JATS XML file to process")

    subparser.add_argument(
        "-o",
        "--output",
        metavar="OUT",
        type=Path,
        required=True,
        help="Output JSON file",
    )

    subparser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable verbose output",
    )

    return subparser


def validate_elife_score_args(parser: ArgumentParser, args: Namespace) -> None:
    """Validate elife-score command arguments."""
    if not args.xml.exists():
        parser.error(f"Input file does not exist: {args.xml}")

    if not args.xml.suffix.lower() in [".xml", ".jats"]:
        parser.error(f"Input file must be XML: {args.xml}")

    if args.output.exists():
        parser.error(f"Output file already exists: {args.output}")


def run_elife_score(parser: ArgumentParser, args: Namespace) -> None:
    """Run the elife-score command."""
    from .parser import extract_elife_assessment
    import dataclasses

    validate_elife_score_args(parser, args)

    if args.verbose:
        print(f"Reading XML: {args.xml}", file=sys.stderr)

    # Extract assessment
    try:
        assessment = extract_elife_assessment(str(args.xml))
    except FileNotFoundError:
        print(f"Error: XML file not found: {args.xml}", file=sys.stderr)
        sys.exit(1)
    except etree.XMLSyntaxError as e:
        print(f"Error: Invalid XML: {e}", file=sys.stderr)
        sys.exit(1)
    except ValueError as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)

    if args.verbose:
        print("\nExtracted:", file=sys.stderr)
        print(f"   Editor: {assessment.editor_name or 'Not found'}", file=sys.stderr)
        print(f"   Affiliation: {assessment.affiliation or 'Not found'}", file=sys.stderr)
        print(f"   Significance: {assessment.findings_significance or 'Not found'}", file=sys.stderr)
        print(f"   Evidence: {assessment.evidence_strength or 'Not found'}", file=sys.stderr)
        if assessment.assessment:
            print(f"   Assessment: {len(assessment.assessment)} chars", file=sys.stderr)
        else:
            print(f"   Assessment: Not found", file=sys.stderr)

    # Write output
    try:
        # Convert dataclass to dict for JSON serialization
        assessment_dict = dataclasses.asdict(assessment)
        json_output = json.dumps(assessment_dict, indent=2, ensure_ascii=False)
        args.output.write_text(json_output, encoding='utf-8')
        print(f"Saved to: {args.output}", file=sys.stderr)
    except Exception as e:
        print(f"Error writing output: {e}", file=sys.stderr)
        sys.exit(1)


def setup_bib_args(subparsers) -> ArgumentParser:
    """Setup the bib command arguments."""
    subparser = subparsers.add_parser(
        "bib",
        description=(
            "Generate BibTeX reference from JATS XML metadata.\n\n"
            "Extracts DOI, title, authors, publication date from JATS XML\n"
            "and generates a properly formatted BibTeX entry.\n\n"
            "Examples:\n"
            "  jats bib paper.xml\n"
            "  jats bib paper.xml -o reference.bib\n"
        ),
        help="Generate BibTeX reference from JATS XML",
        formatter_class=RawTextHelpFormatter,
    )

    subparser.add_argument("xml", type=Path, help="JATS XML file to process")

    subparser.add_argument(
        "-o",
        "--output",
        metavar="OUT",
        type=Path,
        help="Output BibTeX file (default: stdout)",
        default=None,
    )

    return subparser


def validate_bib_args(parser: ArgumentParser, args: Namespace) -> None:
    """Validate bib command arguments."""
    if not args.xml.exists():
        parser.error(f"Input file does not exist: {args.xml}")

    if not args.xml.suffix.lower() in [".xml", ".jats"]:
        parser.error(f"Input file must be XML: {args.xml}")

    if args.output and args.output.exists() and not args.output.is_file():
        parser.error(f"Output path exists but is not a file: {args.output}")


def _escape_latex(text: str) -> str:
    if not text:
        return ""
    for char, esc in [("&", r"\&"), ("%", r"\%"), ("$", r"\$"),
                      ("#", r"\#"), ("_", r"\_"), ("{", r"\{"),
                      ("}", r"\}"), ("~", r"\textasciitilde{}"),
                      ("^", r"\textasciicircum{}")]:
        text = text.replace(char, esc)
    return text


def _find_text(root: etree.Element, *xpaths: str) -> str | None:
    for xpath in xpaths:
        elem = root.find(xpath)
        if elem is not None and elem.text and elem.text.strip():
            return elem.text.strip()
    return None


def run_bib(parser: ArgumentParser, args: Namespace) -> None:
    """Run the bib command."""
    validate_bib_args(parser, args)

    tree = etree.parse(str(args.xml))
    root = tree.getroot()

    doi = parse_doi(root)
    title = parse_title(root)
    pub_date = parse_pub_date(root)
    authors, _ = parse_authors(root)

    journal = _find_text(
        root,
        './/journal-meta/journal-title-group/journal-title',
        './/journal-meta/journal-title',
    )
    publisher = _find_text(root, './/journal-meta/publisher/publisher-name')
    issn = _find_text(
        root,
        './/journal-meta/issn[@pub-type="epub"]',
        './/journal-meta/issn[@pub-type="ppub"]',
        './/journal-meta/issn',
    )
    volume = _find_text(root, './/article-meta/volume')

    if not doi:
        print("Error: No DOI found in XML", file=sys.stderr)
        sys.exit(1)

    year = pub_date[:4] if pub_date else "0000"

    if authors:
        first_surname = authors[0].surname or "Unknown"
        key = re.sub(r'[^a-zA-Z]', '_', first_surname)
    else:
        key = "Unknown"
    bibtex_key = f"{key}_{year}"

    author_strings = []
    for author in sorted(authors, key=lambda x: x.position or 0):
        if author.surname and author.given_names:
            author_strings.append(f"{author.surname}, {author.given_names}")
        elif author.surname:
            author_strings.append(author.surname)
    author_str = " and ".join(author_strings)

    fields = [("title", _escape_latex(title))]
    if volume:
        fields.append(("volume", volume))
    if issn:
        fields.append(("issn", issn))
    fields.append(("url", f"https://doi.org/{doi}"))
    fields.append(("doi", doi.lower()))
    if journal:
        fields.append(("journal", journal))
    if publisher:
        fields.append(("publisher", publisher))
    fields.append(("author", author_str))
    fields.append(("year", year))

    lines = [f"@article{{{bibtex_key},"]
    for i, (name, value) in enumerate(fields):
        suffix = "," if i < len(fields) - 1 else ""
        lines.append(f"  {name:<9} = {{{value}}}{suffix}")
    lines.append("}")

    bibtex = "\n".join(lines) + "\n"

    if args.output:
        args.output.write_text(bibtex, encoding='utf-8')
        print(f"Generated BibTeX: {args.xml} -> {args.output}", file=sys.stderr)
    else:
        print(bibtex)


def setup_parser():
    """Create and configure the main argument parser."""
    parser = ArgumentParser(
        description=f"jats {__version__}: JATS XML to Markdown converter with peer review extraction.",
        formatter_class=RawTextHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<CMD>")

    command_to_parser = {
        "metadata": setup_metadata_args(subparsers),
        "convert": setup_convert_args(subparsers),
        "find": setup_find_args(subparsers),
        "text": setup_text_args(subparsers),
        "annotate": setup_annotate_args(subparsers),
        "elife-score": setup_elife_score_args(subparsers),
        "bib": setup_bib_args(subparsers),
    }

    return parser, command_to_parser


def main() -> None:
    """Main entry point for the jats CLI."""
    parser, command_to_parser = setup_parser()

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    command_map = {
        "metadata": run_metadata,
        "convert": run_convert,
        "find": run_find,
        "text": run_text,
        "annotate": run_annotate,
        "elife-score": run_elife_score,
        "bib": run_bib,
    }

    if args.command in command_map:
        try:
            command_map[args.command](parser, args)
        except Exception as e:
            print(f"Error: {e}", file=sys.stderr)
            sys.exit(1)
    else:
        parser.print_help(sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
