"""Markdown converter for JATS articles."""

from typing import List

from .models import Article, Figure, SubArticle


def format_figure_markdown(figure: Figure, article_id: str = None, is_elife: bool = False) -> str:
    """Format figure as markdown.

    Args:
        figure: Figure object
        article_id: Article ID for constructing eLife URLs
        is_elife: Whether this is an eLife article

    Returns:
        Markdown formatted figure
    """
    parts = []

    label = figure.label or 'Figure'
    caption = figure.caption or ''

    # Determine image path
    image_path = None
    if figure.file_path:
        # Use manifest path if available (bioRxiv)
        image_path = figure.file_path
    elif figure.graphic_href:
        graphic_href = figure.graphic_href

        # For eLife articles, construct web URL
        if is_elife and article_id:
            # Convert .tif to .jpg for web display
            base_filename = graphic_href.replace('.tif', '')
            image_path = (
                f"https://cdn.elifesciences.org/articles/{article_id}/{base_filename}.jpg"
            )
        else:
            image_path = graphic_href

    if image_path:
        parts.append(f"![{label}]({image_path})")
        parts.append("")

    if caption:
        parts.append(f"**{label}:** {caption}")
        parts.append("")

    return '\n'.join(parts)


def convert_to_markdown(article: Article) -> str:
    """Convert Article object to markdown.

    Args:
        article: Article object

    Returns:
        Markdown formatted text
    """
    md_parts = []

    # Title
    if article.title:
        md_parts.append(f"# {article.title}\n")

    # Authors with affiliations and ORCID
    if article.authors:
        md_parts.append("## Authors\n")

        # Create affiliation number mapping
        aff_map = {}
        for idx, (aff_id, aff_text) in enumerate(article.affiliations.items(), 1):
            aff_map[aff_id] = idx

        for author in article.authors:
            author_line = f"{author.given_names} {author.surname}"

            # Add affiliation superscript
            if author.affiliation_id and author.affiliation_id in aff_map:
                aff_num = aff_map[author.affiliation_id]
                author_line += f"<sup>{aff_num}</sup>"

            # Add ORCID
            if author.orcid:
                author_line += f" ([ORCID: {author.orcid}](https://orcid.org/{author.orcid}))"

            # Add corresponding indicator
            if author.corresponding:
                author_line += " †"

            md_parts.append(f"- {author_line}")

        # Add affiliations
        if article.affiliations:
            md_parts.append("\n### Affiliations\n")
            for aff_id, aff_text in article.affiliations.items():
                aff_num = aff_map.get(aff_id, '')
                md_parts.append(f"{aff_num}. {aff_text}")

        md_parts.append("")
        md_parts.append("† Corresponding author\n")

    # Abstract
    if article.abstract:
        md_parts.append("## Abstract\n")
        md_parts.append(article.abstract + "\n")

    # Body sections
    for section in article.body:
        if section.title:
            md_parts.append(f"## {section.title}\n")

        # Render content items (paragraphs and figures in order)
        for item in section.content_items:
            if item.item_type == 'paragraph' and item.text:
                md_parts.append(item.text + "\n")
            elif item.item_type == 'figure' and item.figure:
                md_parts.append(
                    format_figure_markdown(
                        item.figure, article.article_id, article.is_elife
                    )
                )

    return '\n'.join(md_parts)


def convert_review_to_markdown(
    decision_letter: SubArticle, round_num: int
) -> str:
    """Convert a single decision letter (review) to markdown.

    Args:
        decision_letter: SubArticle object containing the decision letter
        round_num: Round number for this review

    Returns:
        Markdown formatted text
    """
    md_parts = []

    # Main heading
    md_parts.append(f"# Peer review - Round {round_num}\n")

    # Show recommendation if available
    if decision_letter.recommendation:
        recommendation_display = decision_letter.recommendation.replace('-', ' ').title()
        md_parts.append(f"**Recommendation:** {recommendation_display}\n")

    # Collect editors and reviewers
    editors = []
    reviewers = []

    for reviewer in decision_letter.reviewers:
        if reviewer.role and ('editor' in reviewer.role.lower()):
            editors.append(reviewer)
        else:
            reviewers.append(reviewer)

    # List editors
    if editors:
        md_parts.append("Editors:")
        for editor in editors:
            editor_line = f"- {editor.given_names} {editor.surname}"

            if editor.orcid:
                editor_line += f" ([ORCID: {editor.orcid}](https://orcid.org/{editor.orcid}))"

            if editor.affiliation:
                editor_line += f", {editor.affiliation}"

            md_parts.append(editor_line)

        md_parts.append("")

    # List reviewers
    md_parts.append("Reviewers:")

    if reviewers:
        for reviewer in reviewers:
            if reviewer.is_anonymous:
                reviewer_line = "- Anonymous Reviewer"
            else:
                reviewer_line = f"- {reviewer.given_names} {reviewer.surname}"

                if reviewer.orcid:
                    reviewer_line += (
                        f" ([ORCID: {reviewer.orcid}](https://orcid.org/{reviewer.orcid}))"
                    )

            if reviewer.affiliation and not reviewer.is_anonymous:
                reviewer_line += f", {reviewer.affiliation}"

            md_parts.append(reviewer_line)
    else:
        md_parts.append("- (Reviewers not individually listed)")

    md_parts.append("")

    # Review text
    md_parts.append("## Review text\n")

    if decision_letter.doi:
        md_parts.append(
            f"DOI: [{decision_letter.doi}](https://doi.org/{decision_letter.doi})\n"
        )

    for section in decision_letter.body:
        for item in section.content_items:
            if item.item_type == 'paragraph' and item.text:
                md_parts.append(item.text + "\n")
            elif item.item_type == 'figure' and item.figure:
                md_parts.append(format_figure_markdown(item.figure, None, False))

    return '\n'.join(md_parts)


def convert_response_to_markdown(
    author_response: SubArticle, article: Article, round_num: int
) -> str:
    """Convert a single author response to markdown.

    Args:
        author_response: SubArticle object containing the author response
        article: Main Article object (for author information)
        round_num: Round number for this response

    Returns:
        Markdown formatted text
    """
    md_parts = []

    # Main heading
    md_parts.append(f"# Author response - Round {round_num}\n")

    # List authors
    md_parts.append("Authors:")

    if article.authors:
        for author in article.authors:
            author_line = f"- {author.given_names} {author.surname}"

            if author.orcid:
                author_line += (
                    f" ([ORCID: {author.orcid}](https://orcid.org/{author.orcid}))"
                )

            md_parts.append(author_line)
    else:
        md_parts.append("- (Authors listed in main article)")

    md_parts.append("")

    # Response text
    md_parts.append("## Response text\n")

    if author_response.doi:
        md_parts.append(
            f"DOI: [{author_response.doi}](https://doi.org/{author_response.doi})\n"
        )

    for section in author_response.body:
        for item in section.content_items:
            if item.item_type == 'paragraph' and item.text:
                md_parts.append(item.text + "\n")
            elif item.item_type == 'figure' and item.figure:
                md_parts.append(format_figure_markdown(item.figure, None, False))

    return '\n'.join(md_parts)
