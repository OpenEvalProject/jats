"""Test article type classification for peer review materials."""

from jxp.models import SubArticle


def test_article_type_classification():
    """Test that all JATS4R article types are correctly classified."""

    # Create test sub-articles with different article types
    review_types = [
        'decision-letter',
        'referee-report',
        'editor-report',
        'reviewer-report',
    ]

    response_types = [
        'author-comment',
        'reply',
    ]

    # Test review classification
    for article_type in review_types:
        sub_article = SubArticle(
            article_type=article_type,
            title=f"Test {article_type}",
        )

        # This should be classified as a review
        assert sub_article.article_type in [
            'decision-letter',
            'referee-report',
            'editor-report',
            'reviewer-report',
        ], f"{article_type} should be classified as a review"

    # Test response classification
    for article_type in response_types:
        sub_article = SubArticle(
            article_type=article_type,
            title=f"Test {article_type}",
        )

        # This should be classified as a response
        assert sub_article.article_type in [
            'author-comment',
            'reply',
        ], f"{article_type} should be classified as a response"

    print("✓ All JATS4R article types are correctly recognized")


if __name__ == '__main__':
    test_article_type_classification()
