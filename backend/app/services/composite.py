"""Normalize sub-metrics to 0-100 risk contributions and combine into a composite score.

Higher contribution = more risky. Thresholds are conservative, general-purpose
defaults; calibration can be moved to a config later.
"""
from __future__ import annotations

from typing import List, Tuple

from ..models.schemas import MarketMetrics, SentimentRiskMetrics
from ..utils.stats import piecewise_score


# --- Market normalization ---

def _market_contributions(m: MarketMetrics) -> List[float]:
    contribs: List[float] = []

    if m.vol_ann_1y is not None:
        # 15% ann vol -> 20, 40% -> 80, 60%+ -> 100
        contribs.append(piecewise_score(m.vol_ann_1y, 0.10, 0.60))

    if m.downside_deviation_ann is not None:
        contribs.append(piecewise_score(m.downside_deviation_ann, 0.08, 0.50))

    if m.var_95_hist_1d is not None:
        # var is negative (loss); -1% -> 10, -5% -> 90
        contribs.append(piecewise_score(-m.var_95_hist_1d, 0.01, 0.06))

    if m.cvar_95_1d is not None:
        contribs.append(piecewise_score(-m.cvar_95_1d, 0.02, 0.08))

    if m.max_drawdown is not None:
        contribs.append(piecewise_score(-m.max_drawdown, 0.10, 0.60))

    if m.beta is not None:
        contribs.append(piecewise_score(abs(m.beta), 0.5, 2.0))

    if m.atr14_pct is not None:
        contribs.append(piecewise_score(m.atr14_pct, 0.01, 0.06))

    if m.gap_risk_freq is not None:
        contribs.append(piecewise_score(m.gap_risk_freq, 0.02, 0.15))

    if m.excess_kurtosis is not None:
        contribs.append(piecewise_score(m.excess_kurtosis, 0.0, 6.0))

    if m.skew is not None:
        # Negative skew is risky; flip sign.
        contribs.append(piecewise_score(-m.skew, -0.5, 1.5))

    if m.liquidity_score is not None:
        # Invert liquidity (high liq = low risk).
        contribs.append(100.0 - float(m.liquidity_score))

    # Sharpe (higher = less risky, invert)
    if m.sharpe is not None:
        contribs.append(piecewise_score(-m.sharpe, -1.5, 1.0))

    return contribs


def _sentiment_contributions(s: SentimentRiskMetrics) -> List[float]:
    contribs: List[float] = []

    if s.negative_ratio is not None:
        contribs.append(piecewise_score(s.negative_ratio, 0.10, 0.50))

    if s.dispersion is not None:
        contribs.append(piecewise_score(s.dispersion, 0.20, 0.70))

    if s.momentum_24h_vs_7d is not None:
        # Negative momentum is risky; flip sign and scale.
        contribs.append(piecewise_score(-s.momentum_24h_vs_7d, -0.3, 0.6))

    if s.news_volume_zscore is not None:
        # Spikes above baseline = event risk.
        contribs.append(piecewise_score(abs(s.news_volume_zscore), 0.5, 3.0))

    if s.source_concentration_hhi is not None:
        contribs.append(piecewise_score(s.source_concentration_hhi, 0.25, 0.85))

    if s.confidence is not None:
        # Low confidence = more risk; invert.
        contribs.append(piecewise_score(1.0 - s.confidence, 0.1, 0.6))

    if s.extreme_score_share is not None:
        contribs.append(piecewise_score(s.extreme_score_share, 0.15, 0.60))

    if s.polarity_gap is not None:
        # Strong polarity in either direction = conviction; invert (low gap = risky).
        contribs.append(piecewise_score(1.0 - s.polarity_gap, 0.4, 0.95))

    if s.sentiment_vol_proxy is not None:
        contribs.append(piecewise_score(s.sentiment_vol_proxy, 0.1, 1.5))

    if s.recency_weighted_sentiment is not None:
        # Negative recency-weighted tilt is risky.
        contribs.append(piecewise_score(-s.recency_weighted_sentiment, -0.3, 0.6))

    return contribs


def _avg(xs: List[float]) -> float:
    return float(sum(xs) / len(xs)) if xs else 50.0


def compute_indices(
    market: MarketMetrics, sentiment: SentimentRiskMetrics
) -> Tuple[float, float]:
    return _avg(_market_contributions(market)), _avg(_sentiment_contributions(sentiment))


def dynamic_sentiment_weight(
    total_articles: int,
    confidence: float,
    base_weight: float = 0.3,
    min_weight: float = 0.1,
    max_weight: float = 0.45,
) -> float:
    """Scale sentiment weight based on data quality.

    - More articles + higher confidence → weight approaches max_weight (0.45).
    - Sparse data (< 5 articles) or low confidence (< 0.4) → weight drops toward min_weight.
    - Default (base) weight stays at 0.3 with moderate data.
    """
    article_factor = min(1.0, total_articles / 20.0)   # 0→0, 20+→1.0
    confidence_factor = max(0.0, min(1.0, (confidence - 0.4) / 0.4))  # 0.4→0, 0.8→1.0
    quality = (article_factor + confidence_factor) / 2.0
    weight = min_weight + quality * (max_weight - min_weight)
    return round(float(weight), 3)


def composite_score(
    market_idx: float, sentiment_idx: float, w_market: float = 0.7, w_sentiment: float = 0.3
) -> float:
    total = w_market + w_sentiment
    if total == 0:
        return 50.0
    return float((w_market * market_idx + w_sentiment * sentiment_idx) / total)


def bucket(score: float) -> str:
    if score < 34:
        return "low"
    if score < 67:
        return "moderate"
    return "high"
