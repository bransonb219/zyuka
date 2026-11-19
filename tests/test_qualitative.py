"""Tests for zyuka.analysis.qualitative (Phase 3)."""

from __future__ import annotations

from zyuka.analysis.qualitative import (
    analyse_sentiment,
    build_codebook,
    cluster_responses,
    extract_themes,
    sentiment_result,
)

POSITIVE_RESPONSES = [
    "The training was excellent and very helpful for our community",
    "Great support from the team, I feel safe and respected",
    "I appreciate the fair treatment and clean facilities",
    "Thanks to the project, access to water has improved",
    "Very satisfied with the useful workshops and friendly staff",
    "The workshops were effective and the staff were friendly",
    "I love how accessible the clinic has become",
]
NEGATIVE_RESPONSES = [
    "The service was poor and the staff were rude",
    "There is a problem with the clinic, it is slow and dirty",
    "I am unhappy about the corruption and bribes demanded",
    "The water pump is broken and unsafe for children",
    "I complain about the late delivery and the missing items",
    "The clinic is unfair and hard to reach for the elderly",
    "I am worried about the failure to provide basic medicine",
]


def _corpus() -> list[str]:
    return POSITIVE_RESPONSES + NEGATIVE_RESPONSES


def test_extract_themes_returns_terms_from_corpus() -> None:
    result = extract_themes(_corpus(), n_themes=8)
    assert result.n == len(_corpus())
    themes = result.details["themes"]
    assert 1 <= len(themes) <= 8
    assert all("term" in t and "mean_tfidf" in t for t in themes)


def test_extract_themes_too_few_responses() -> None:
    result = extract_themes(["hello", "world"])
    assert "Need at least" in result.summary


def test_cluster_responses_assigns_all_responses() -> None:
    result = cluster_responses(_corpus(), n_clusters=3)
    clusters = result.details["clusters"]
    assert len(clusters) >= 2
    assert sum(c["size"] for c in clusters) == result.n
    assert all("label_terms" in c for c in clusters)


def test_sentiment_separates_positive_and_negative() -> None:
    report = analyse_sentiment(_corpus())
    assert report.counts.get("positive", 0) >= 3
    assert report.counts.get("negative", 0) >= 3


def test_sentiment_handles_negation() -> None:
    report = analyse_sentiment(["The service was not good", "The staff were not rude"])
    # "not good" should flip to negative; "not rude" should flip to positive.
    scores = {r["index"]: r["score"] for r in report.per_response}
    assert scores[0] < 0
    assert scores[1] > 0


def test_sentiment_result_wrap_has_counts_and_summary() -> None:
    result = sentiment_result(_corpus())
    assert result.n == len(_corpus())
    assert "positive" in result.details["counts"] or "negative" in result.details["counts"]
    assert "positive=" in result.summary


def test_build_codebook_returns_codes_with_examples() -> None:
    result = build_codebook(_corpus(), n_themes=5)
    codes = result.details["codes"]
    assert 1 <= len(codes) <= 5
    for code in codes:
        assert "code" in code
        assert "examples" in code
        assert len(code["examples"]) <= 3
