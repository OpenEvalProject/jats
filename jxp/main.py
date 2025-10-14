"""Main CLI entry point for jxp."""

import sys
from argparse import ArgumentParser, Namespace, RawTextHelpFormatter
from pathlib import Path

from . import __version__
from .converter import (
    convert_response_to_markdown,
    convert_review_to_markdown,
    convert_to_markdown,
)
from .parser import parse_jats_xml


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
            "Base path for extracting peer review materials (creates <path>_reviews.md and <path>_responses.md). "
            "Extracts sub-articles with article-type: decision-letter, referee-report, editor-report, "
            "reviewer-report, author-comment, or reply. Reviews and responses are organized by revision round "
            "from JATS4R custom-meta 'peer-review-revision-round' (defaults to round 1 if not specified)."
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

    # Output
    if args.output:
        args.output.write_text(markdown, encoding='utf-8')
        print(f"Converted {args.xml} -> {args.output}", file=sys.stderr)
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

                # JATS4R article types for reviews/reports
                if sub_article.article_type in [
                    'decision-letter',
                    'referee-report',
                    'editor-report',
                    'reviewer-report',
                ]:
                    decision_letters.append(sub_article)
                # JATS4R article types for author responses
                elif sub_article.article_type in ['author-comment', 'reply']:
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

                # Combine all reviews into a single file
                if reviews_by_round:
                    review_path = Path(f"{args.reviews}_reviews.md")
                    review_parts = []

                    for round_num in sorted(reviews_by_round.keys()):
                        for review in reviews_by_round[round_num]:
                            review_markdown = convert_review_to_markdown(review, round_num)
                            review_parts.append(review_markdown)
                            review_parts.append("\n---\n")  # Separator between reviews

                    # Remove last separator
                    if review_parts and review_parts[-1] == "\n---\n":
                        review_parts.pop()

                    review_path.write_text('\n'.join(review_parts), encoding='utf-8')
                    print(f"Extracted reviews -> {review_path}", file=sys.stderr)

                # Combine all responses into a single file
                if responses_by_round:
                    response_path = Path(f"{args.reviews}_responses.md")
                    response_parts = []

                    for round_num in sorted(responses_by_round.keys()):
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
                    print(f"Extracted responses -> {response_path}", file=sys.stderr)
        else:
            print(
                f"Warning: No sub-articles found in {args.xml}",
                file=sys.stderr,
            )


def setup_parser():
    """Create and configure the main argument parser."""
    parser = ArgumentParser(
        description=f"jxp {__version__}: JATS XML Parser for scientific articles.",
        formatter_class=RawTextHelpFormatter,
    )

    subparsers = parser.add_subparsers(dest="command", metavar="<CMD>")

    command_to_parser = {
        "convert": setup_convert_args(subparsers),
    }

    return parser, command_to_parser


def main() -> None:
    """Main entry point for the jxp CLI."""
    parser, command_to_parser = setup_parser()

    if len(sys.argv) == 1:
        parser.print_help(sys.stderr)
        sys.exit(1)

    args = parser.parse_args()

    command_map = {
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
