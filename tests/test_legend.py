"""The corresponding-author legend must only appear when an author is marked."""

from jats.converter import convert_to_markdown
from jats.models import Article, Author


def test_legend_absent_without_corresponding_author():
    article = Article(
        title="Sample",
        authors=[Author(given_names="Jane", surname="Doe")],
    )
    markdown = convert_to_markdown(article)
    assert "Corresponding author" not in markdown


def test_legend_present_with_corresponding_author():
    article = Article(
        title="Sample",
        authors=[Author(given_names="Jane", surname="Doe", corresponding=True)],
    )
    markdown = convert_to_markdown(article)
    assert "Corresponding author" in markdown
    assert "\u2020" in markdown
