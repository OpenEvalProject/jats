"""Main CLI entry point for jats."""

import json
import sys
from argparse import ArgumentParser, Namespace, RawTextHelpFormatter
from pathlib import Path

from . import __version__
from .converter import (
    convert_response_to_markdown,
    convert_review_to_markdown,
    convert_to_markdown,
)
from .parser import parse_jats_xml, parse_doi, parse_title, parse_abstract, parse_pub_date
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

    # Extract metadata
    doi = parse_doi(root)
    title = parse_title(root)
    abstract = parse_abstract(root)
    pub_date = parse_pub_date(root)

    # Create metadata dictionary
    metadata = {
        "doi": doi,
        "title": title,
        "abstract": abstract,
        "pub_date": pub_date
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
        "-m",
        "--manifest",
        type=Path,
        help="Optional manifest.xml file (bioRxiv)",
        default=None,
    )

    subparser.add_argument(
        "-r",
        "--reviews",
        type=str,
        help=(
            "Base name for extracting peer review materials (creates reviews_v1.md, reviews_v2.md and "
            "responses_v1.md, responses_v2.md). Extracts sub-articles with article-type: decision-letter, "
            "referee-report, editor-report, reviewer-report, author-comment, or reply. Reviews and responses "
            "are organized by revision round from JATS4R custom-meta 'peer-review-revision-round' (defaults "
            "to round 1 if not specified)."
        ),
        default=None,
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

    if args.manifest:
        if not args.manifest.exists():
            parser.error(f"Manifest file does not exist: {args.manifest}")


def run_convert(parser: ArgumentParser, args: Namespace) -> None:
    """Run the convert command."""
    validate_convert_args(parser, args)

    # Parse JATS XML
    article = parse_jats_xml(args.xml, manifest_path=args.manifest)

    # Convert to markdown
    markdown = convert_to_markdown(article)

    # Determine manuscript version (default to v1 if no sub-articles or revision info)
    manuscript_version = 1
    if article.sub_articles:
        # Get the maximum revision round from sub-articles
        revision_rounds = [sa.revision_round for sa in article.sub_articles if sa.revision_round is not None]
        if revision_rounds:
            manuscript_version = max(revision_rounds)

    # Output with version in filename
    if args.output:
        # Add version to output filename
        output_path = Path(args.output)
        output_stem = output_path.stem
        output_suffix = output_path.suffix
        versioned_output = output_path.parent / f"{output_stem}_v{manuscript_version}{output_suffix}"

        versioned_output.write_text(markdown, encoding='utf-8')
        print(f"Converted {args.xml} -> {versioned_output}", file=sys.stderr)
    else:
        print(markdown)

    # Handle reviewer comments if requested
    if args.reviews:
        if article.sub_articles:
            # Separate decision letters and author responses
            # Based on JATS4R recommendations for peer review materials
            decision_letters = []
            author_responses = []

            for sub_article in article.sub_articles:
                # Default to round 1 if no revision_round specified
                if sub_article.revision_round is None:
                    sub_article.revision_round = 1

                # JATS4R article types for reviews/reports (including editor decisions)
                if sub_article.article_type in [
                    'decision-letter',      # Editor decision, treated as reviewer
                    'editor-report',        # Editor report, treated as reviewer
                    'referee-report',       # Reviewer report
                    'article-commentary',   # Reviewer report
                ]:
                    decision_letters.append(sub_article)
                # JATS4R article types for author responses
                elif sub_article.article_type in [
                    'reply',                # Author response
                    'author-comment',       # Author response
                ]:
                    author_responses.append(sub_article)

            if not decision_letters and not author_responses:
                print(
                    f"Warning: No review/response content found in {args.xml}",
                    file=sys.stderr,
                )
            else:
                # Group reviews by revision round
                reviews_by_round = {}
                for review in decision_letters:
                    round_num = review.revision_round
                    if round_num not in reviews_by_round:
                        reviews_by_round[round_num] = []
                    reviews_by_round[round_num].append(review)

                # Group responses by revision round
                responses_by_round = {}
                for response in author_responses:
                    round_num = response.revision_round
                    if round_num not in responses_by_round:
                        responses_by_round[round_num] = []
                    responses_by_round[round_num].append(response)

                # Output separate review files per revision round
                if reviews_by_round:
                    for round_num in sorted(reviews_by_round.keys()):
                        # Extract directory and base name from args.reviews
                        review_base = Path(args.reviews)
                        review_dir = review_base.parent
                        review_name = review_base.name

                        review_path = review_dir / f"reviews_v{round_num}.md"
                        review_parts = []

                        for review in reviews_by_round[round_num]:
                            review_markdown = convert_review_to_markdown(review, round_num)
                            review_parts.append(review_markdown)
                            review_parts.append("\n---\n")  # Separator between reviews

                        # Remove last separator
                        if review_parts and review_parts[-1] == "\n---\n":
                            review_parts.pop()

                        review_path.write_text('\n'.join(review_parts), encoding='utf-8')
                        print(f"Extracted reviews (round {round_num}) -> {review_path}", file=sys.stderr)

                # Output separate response files per revision round
                if responses_by_round:
                    for round_num in sorted(responses_by_round.keys()):
                        # Extract directory and base name from args.reviews
                        response_base = Path(args.reviews)
                        response_dir = response_base.parent
                        response_name = response_base.name

                        response_path = response_dir / f"responses_v{round_num}.md"
                        response_parts = []

                        for response in responses_by_round[round_num]:
                            response_markdown = convert_response_to_markdown(
                                response, article, round_num
                            )
                            response_parts.append(response_markdown)
                            response_parts.append("\n---\n")  # Separator between responses

                        # Remove last separator
                        if response_parts and response_parts[-1] == "\n---\n":
                            response_parts.pop()

                        response_path.write_text('\n'.join(response_parts), encoding='utf-8')
                        print(f"Extracted responses (round {round_num}) -> {response_path}", file=sys.stderr)
        else:
            print(
                f"Warning: No sub-articles found in {args.xml}",
                file=sys.stderr,
            )


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
