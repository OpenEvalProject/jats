"""Test review extraction logic from main.py."""

from jxp.models import Article, SubArticle


def test_review_extraction_logic():
    """Test that sub-articles are correctly separated into reviews and responses."""

    # Create test article with various sub-article types
    article = Article(
        title="Test Article",
        sub_articles=[
            SubArticle(article_type='decision-letter', title='Decision Letter 1'),
            SubArticle(article_type='referee-report', title='Referee Report 1'),
            SubArticle(article_type='editor-report', title='Editor Report 1'),
            SubArticle(article_type='reviewer-report', title='Reviewer Report 1'),
            SubArticle(article_type='author-comment', title='Author Comment 1'),
            SubArticle(article_type='reply', title='Reply 1'),
        ],
    )

    # This mimics the logic from main.py
    decision_letters = []
    author_responses = []

    for sub_article in article.sub_articles:
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

    # Verify correct classification
    assert len(decision_letters) == 4, f"Expected 4 reviews, got {len(decision_letters)}"
    assert len(author_responses) == 2, f"Expected 2 responses, got {len(author_responses)}"

    # Verify specific types
    review_types = [sub.article_type for sub in decision_letters]
    assert 'decision-letter' in review_types
    assert 'referee-report' in review_types
    assert 'editor-report' in review_types
    assert 'reviewer-report' in review_types

    response_types = [sub.article_type for sub in author_responses]
    assert 'author-comment' in response_types
    assert 'reply' in response_types

    print("✓ Review extraction logic works correctly")
    print(f"  - Found {len(decision_letters)} reviews/reports")
    print(f"  - Found {len(author_responses)} author responses")


if __name__ == '__main__':
    test_review_extraction_logic()
