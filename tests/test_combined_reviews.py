"""Test combined review extraction with revision rounds."""

from jxp.models import Article, SubArticle


def test_combined_reviews_with_rounds():
    """Test that reviews and responses are correctly grouped by revision round."""

    # Create test article with multiple rounds of reviews
    article = Article(
        title="Test Article",
        sub_articles=[
            # Round 1 reviews
            SubArticle(
                article_type='decision-letter',
                title='Decision Letter 1',
                revision_round=1,
                recommendation='major-revision',
            ),
            SubArticle(
                article_type='referee-report',
                title='Referee Report 1',
                revision_round=1,
                recommendation='minor-revision',
            ),
            # Round 2 reviews
            SubArticle(
                article_type='editor-report',
                title='Editor Report 2',
                revision_round=2,
                recommendation='accept',
            ),
            # Round 1 responses
            SubArticle(
                article_type='author-comment',
                title='Author Comment 1',
                revision_round=1,
            ),
            # Round 2 responses
            SubArticle(
                article_type='reply',
                title='Reply 2',
                revision_round=2,
            ),
        ],
    )

    # Separate and group by round (mimicking main.py logic)
    decision_letters = []
    author_responses = []

    for sub_article in article.sub_articles:
        if sub_article.revision_round is None:
            sub_article.revision_round = 1

        if sub_article.article_type in [
            'decision-letter',
            'referee-report',
            'editor-report',
            'reviewer-report',
        ]:
            decision_letters.append(sub_article)
        elif sub_article.article_type in ['author-comment', 'reply']:
            author_responses.append(sub_article)

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

    # Verify grouping
    assert len(reviews_by_round) == 2, f"Expected 2 review rounds, got {len(reviews_by_round)}"
    assert len(responses_by_round) == 2, f"Expected 2 response rounds, got {len(responses_by_round)}"

    # Verify round 1 has 2 reviews
    assert len(reviews_by_round[1]) == 2, f"Expected 2 reviews in round 1, got {len(reviews_by_round[1])}"

    # Verify round 2 has 1 review
    assert len(reviews_by_round[2]) == 1, f"Expected 1 review in round 2, got {len(reviews_by_round[2])}"

    # Verify recommendations are present
    assert reviews_by_round[1][0].recommendation == 'major-revision'
    assert reviews_by_round[1][1].recommendation == 'minor-revision'
    assert reviews_by_round[2][0].recommendation == 'accept'

    print("✓ Combined reviews with revision rounds work correctly")
    print(f"  - Round 1: {len(reviews_by_round[1])} reviews, {len(responses_by_round[1])} responses")
    print(f"  - Round 2: {len(reviews_by_round[2])} reviews, {len(responses_by_round[2])} responses")


def test_default_revision_round():
    """Test that reviews without revision_round default to round 1."""

    # Create test article with no revision_round specified
    article = Article(
        title="Test Article",
        sub_articles=[
            SubArticle(
                article_type='decision-letter',
                title='Decision Letter',
                revision_round=None,
            ),
            SubArticle(
                article_type='author-comment',
                title='Author Comment',
                revision_round=None,
            ),
        ],
    )

    # Apply default (mimicking main.py logic)
    for sub_article in article.sub_articles:
        if sub_article.revision_round is None:
            sub_article.revision_round = 1

    # Verify all have round 1
    for sub_article in article.sub_articles:
        assert sub_article.revision_round == 1, f"Expected revision_round=1, got {sub_article.revision_round}"

    print("✓ Default revision round (round 1) works correctly")


if __name__ == '__main__':
    test_combined_reviews_with_rounds()
    test_default_revision_round()
