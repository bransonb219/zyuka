"""Phase 3 — qualitative analysis for free-text survey responses.

Three pure functions keep the layer honest:

* :func:`extract_themes` — TF-IDF over the response corpus, returns the
  top terms (unigrams + bigrams) with document frequency and a mean
  TF-IDF score.
* :func:`cluster_responses` — K-means on the TF-IDF matrix to group
  similar responses; each cluster is labelled by its top distinctive
  terms. Hierarchical linkage distances are also returned so a reviewer
  can see how clusters relate.
* :func:`analyse_sentiment` — a bundled, VADER-style lexicon classifies
  each response as ``positive`` / ``neutral`` / ``negative``. The
  lexicon is small and English-only; it's a starting point, not a
  substitute for human review.
* :func:`build_codebook` — organises the themes into a hierarchical
  code-book draft a researcher can hand-edit.

Everything is local-only. No model downloads; no network calls. Non-
English responses will degrade gracefully (fewer sentiment matches) —
the honest output is "neutral" rather than a false positive.
"""

from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field
from typing import Any

import numpy as np
from scipy.cluster.hierarchy import linkage
from sklearn.cluster import KMeans
from sklearn.feature_extraction.text import TfidfVectorizer

from zyuka.analysis.tests import AnalysisResult

MIN_TEXTS = 10
MIN_WORDS_PER_TEXT = 1

# A small VADER-inspired lexicon. Each entry: term → polarity in [-1, 1].
# Kept intentionally compact; teams layer domain words via extend_lexicon().
POSITIVE_LEXICON: dict[str, float] = {
    "good": 0.6,
    "great": 0.8,
    "excellent": 0.9,
    "love": 0.9,
    "helpful": 0.7,
    "satisfied": 0.7,
    "happy": 0.7,
    "positive": 0.6,
    "improve": 0.4,
    "safe": 0.6,
    "useful": 0.6,
    "better": 0.5,
    "best": 0.9,
    "support": 0.5,
    "clean": 0.4,
    "fair": 0.4,
    "easy": 0.5,
    "trust": 0.6,
    "accessible": 0.5,
    "effective": 0.7,
    "efficient": 0.6,
    "respectful": 0.7,
    "friendly": 0.6,
    "thank": 0.6,
    "thanks": 0.6,
    "appreciate": 0.7,
    "benefit": 0.6,
    "progress": 0.5,
    "solved": 0.6,
    "resolved": 0.6,
    "working": 0.4,
    "yes": 0.3,
}
NEGATIVE_LEXICON: dict[str, float] = {
    "bad": -0.6,
    "poor": -0.6,
    "worst": -0.9,
    "hate": -0.9,
    "difficult": -0.5,
    "hard": -0.4,
    "slow": -0.4,
    "late": -0.4,
    "delay": -0.5,
    "unsafe": -0.7,
    "unhappy": -0.7,
    "dissatisfied": -0.7,
    "complaint": -0.6,
    "complain": -0.6,
    "problem": -0.5,
    "issue": -0.4,
    "concern": -0.4,
    "worried": -0.5,
    "fear": -0.6,
    "angry": -0.7,
    "frustrated": -0.7,
    "rude": -0.7,
    "corrupt": -0.8,
    "bribe": -0.8,
    "stolen": -0.8,
    "broken": -0.5,
    "fail": -0.6,
    "failed": -0.6,
    "failure": -0.6,
    "missing": -0.4,
    "lost": -0.4,
    "danger": -0.7,
    "unfair": -0.7,
}
NEGATION_WORDS: set[str] = {
    "not",
    "never",
    "no",
    "none",
    "without",
    "cannot",
    "can't",
    "didn't",
    "don't",
}


@dataclass
class Theme:
    """A theme: one or more terms that frequently co-occur in responses."""

    term: str
    document_frequency: int
    mean_tfidf: float
    example_indices: list[int] = field(default_factory=list)


@dataclass
class SentimentReport:
    """Sentiment breakdown across a corpus."""

    counts: dict[str, int] = field(default_factory=dict)
    mean_score: float = 0.0
    per_response: list[dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "counts": self.counts,
            "mean_score": self.mean_score,
            "per_response": self.per_response,
        }


_WORD_RE = re.compile(r"[A-Za-z][A-Za-z'-]{1,}")


def _tokenize(text: str) -> list[str]:
    return [m.group(0).lower() for m in _WORD_RE.finditer(text)]


def _clean_corpus(texts: Iterable[str]) -> list[str]:
    cleaned: list[str] = []
    for t in texts:
        if t is None:
            continue
        text = str(t).strip()
        if len(text.split()) < MIN_WORDS_PER_TEXT:
            continue
        cleaned.append(text)
    return cleaned


def extract_themes(
    texts: Iterable[str],
    n_themes: int = 15,
    ngram_range: tuple[int, int] = (1, 2),
    min_df: int = 2,
    max_df: float = 0.9,
) -> AnalysisResult:
    """Return the top ``n_themes`` terms/phrases by mean TF-IDF.

    Short responses (fewer than ``MIN_WORDS_PER_TEXT`` words) are
    dropped silently so blank cells don't dilute the vocabulary.
    """

    corpus = _clean_corpus(texts)
    result = AnalysisResult(name="Theme extraction (TF-IDF)", kind="themes")
    result.n = len(corpus)
    if result.n < MIN_TEXTS:
        result.summary = f"Need at least {MIN_TEXTS} responses; got {result.n}."
        return result
    try:
        vec = TfidfVectorizer(
            ngram_range=ngram_range,
            stop_words="english",
            min_df=min_df,
            max_df=max_df,
            token_pattern=r"(?u)\b[A-Za-z][A-Za-z'-]+\b",
        )
        matrix = vec.fit_transform(corpus)
    except ValueError as exc:
        result.summary = f"TF-IDF failed: {exc}"
        return result

    terms = vec.get_feature_names_out()
    tfidf = np.asarray(matrix.mean(axis=0)).flatten()
    doc_freq = np.asarray((matrix > 0).sum(axis=0)).flatten()
    order = np.argsort(tfidf)[::-1][:n_themes]
    themes: list[dict[str, Any]] = []
    for idx in order:
        themes.append(
            {
                "term": str(terms[idx]),
                "mean_tfidf": float(tfidf[idx]),
                "document_frequency": int(doc_freq[idx]),
            }
        )
    result.details["themes"] = themes
    result.metrics = {"vocab_size": float(len(terms))}
    result.summary = f"Top {len(themes)} themes across {result.n} responses."
    return result


def cluster_responses(
    texts: Iterable[str],
    n_clusters: int = 5,
    ngram_range: tuple[int, int] = (1, 2),
    random_state: int = 42,
) -> AnalysisResult:
    """Cluster responses via K-means on a TF-IDF matrix.

    Each cluster is labelled by the top distinctive terms (highest
    mean TF-IDF within the cluster minus the corpus-wide mean).
    Hierarchical linkage is also returned so a reviewer can see which
    clusters are closest to each other.
    """

    corpus = _clean_corpus(texts)
    result = AnalysisResult(name="Response clustering", kind="clustering_qualitative")
    result.n = len(corpus)
    if result.n < max(MIN_TEXTS, n_clusters * 2):
        result.summary = f"Need at least {max(MIN_TEXTS, n_clusters * 2)} responses."
        return result
    vec = TfidfVectorizer(
        ngram_range=ngram_range,
        stop_words="english",
        min_df=2,
        max_df=0.9,
        token_pattern=r"(?u)\b[A-Za-z][A-Za-z'-]+\b",
    )
    try:
        matrix = vec.fit_transform(corpus)
    except ValueError as exc:
        result.summary = f"TF-IDF failed: {exc}"
        return result
    terms = vec.get_feature_names_out()
    dense = matrix.toarray()
    n_clusters = max(2, min(n_clusters, result.n - 1))
    model = KMeans(n_clusters=n_clusters, random_state=random_state, n_init=10)
    labels = model.fit_predict(dense)
    overall_mean = dense.mean(axis=0)
    clusters: list[dict[str, Any]] = []
    for c in range(n_clusters):
        mask = labels == c
        if mask.sum() == 0:
            continue
        cluster_mean = dense[mask].mean(axis=0)
        distinctive = np.argsort(cluster_mean - overall_mean)[::-1][:5]
        label_terms = [str(terms[i]) for i in distinctive]
        clusters.append(
            {
                "cluster": int(c),
                "size": int(mask.sum()),
                "label_terms": label_terms,
                "example_indices": [int(i) for i in np.where(mask)[0][:3]],
            }
        )
    # Linkage on centroids so the UI can draw a dendrogram if desired.
    try:
        linkage_matrix = linkage(model.cluster_centers_, method="average", metric="cosine")
        result.details["linkage"] = linkage_matrix.tolist()
    except ValueError:
        pass
    result.details["clusters"] = clusters
    result.metrics = {"k": float(n_clusters), "inertia": float(model.inertia_)}
    result.summary = f"{n_clusters} response clusters across {result.n} responses."
    return result


def analyse_sentiment(
    texts: Iterable[str],
    extend_lexicon: dict[str, float] | None = None,
) -> SentimentReport:
    """Lexicon-based sentiment scoring (``positive`` / ``neutral`` / ``negative``).

    Scores sum the polarity of matched tokens, dampen by negation (the
    previous word being in :data:`NEGATION_WORDS` flips the sign), and
    normalise by the square-root of token count so long responses don't
    dominate. Thresholds: ``> 0.1`` → positive, ``< -0.1`` → negative.
    """

    positive = dict(POSITIVE_LEXICON)
    negative = dict(NEGATIVE_LEXICON)
    if extend_lexicon:
        for term, polarity in extend_lexicon.items():
            if polarity >= 0:
                positive[term.lower()] = polarity
            else:
                negative[term.lower()] = polarity

    counts: Counter[str] = Counter()
    scored: list[dict[str, Any]] = []
    total_score = 0.0
    for idx, raw in enumerate(texts):
        text = str(raw or "").strip()
        tokens = _tokenize(text)
        if not tokens:
            counts["neutral"] += 1
            scored.append({"index": idx, "label": "neutral", "score": 0.0})
            continue
        polarity = 0.0
        for i, token in enumerate(tokens):
            prev = tokens[i - 1] if i > 0 else ""
            sign = -1.0 if prev in NEGATION_WORDS else 1.0
            if token in positive:
                polarity += sign * positive[token]
            elif token in negative:
                polarity += sign * negative[token]
        normalised = polarity / (np.sqrt(len(tokens)) or 1.0)
        label = "positive" if normalised > 0.1 else "negative" if normalised < -0.1 else "neutral"
        counts[label] += 1
        scored.append({"index": idx, "label": label, "score": float(normalised)})
        total_score += float(normalised)
    report = SentimentReport(
        counts=dict(counts),
        mean_score=(total_score / len(scored)) if scored else 0.0,
        per_response=scored,
    )
    return report


def sentiment_result(
    texts: Iterable[str],
    extend_lexicon: dict[str, float] | None = None,
) -> AnalysisResult:
    """Wrap :func:`analyse_sentiment` in an :class:`AnalysisResult`."""

    report = analyse_sentiment(texts, extend_lexicon=extend_lexicon)
    result = AnalysisResult(name="Sentiment (lexicon)", kind="sentiment")
    result.n = sum(report.counts.values())
    result.details["counts"] = report.counts
    result.details["per_response"] = report.per_response[:200]
    result.metrics = {
        "mean_score": float(report.mean_score),
        "positive": float(report.counts.get("positive", 0)),
        "negative": float(report.counts.get("negative", 0)),
        "neutral": float(report.counts.get("neutral", 0)),
    }
    if result.n:
        pct = {k: v / result.n * 100.0 for k, v in report.counts.items()}
        parts = [f"{k}={pct.get(k, 0):.0f}%" for k in ("positive", "neutral", "negative")]
        result.summary = f"{' · '.join(parts)} across {result.n} responses (mean score {report.mean_score:+.2f})."
    else:
        result.summary = "No responses to score."
    return result


def build_codebook(
    texts: Iterable[str],
    themes: Sequence[dict[str, Any]] | None = None,
    n_themes: int = 15,
) -> AnalysisResult:
    """Group themes + example responses into a code-book draft.

    If ``themes`` isn't provided, :func:`extract_themes` runs first.
    Each code includes the term, document frequency and up to three
    short example responses containing the term — the artefact a
    qualitative researcher would hand-edit in Excel.
    """

    corpus = _clean_corpus(texts)
    result = AnalysisResult(name="Code-book draft", kind="codebook")
    result.n = len(corpus)
    if themes is None:
        extracted = extract_themes(corpus, n_themes=n_themes)
        themes = extracted.details.get("themes", [])

    codes: list[dict[str, Any]] = []
    for theme in themes or []:
        term = str(theme["term"])
        hits = [(i, text) for i, text in enumerate(corpus) if term in text.lower()][:3]
        codes.append(
            {
                "code": term,
                "document_frequency": int(theme.get("document_frequency", 0)),
                "mean_tfidf": float(theme.get("mean_tfidf", 0.0)),
                "examples": [t[:220] for _, t in hits],
            }
        )
    result.details["codes"] = codes
    result.metrics = {"codes": float(len(codes))}
    result.summary = f"Code-book draft with {len(codes)} codes across {result.n} responses."
    return result
