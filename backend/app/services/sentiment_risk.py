"""Sentiment-derived risk sub-metrics computed from SentimentResponse."""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List, Optional

import numpy as np
from dateutil import parser as dateparser

from ..models.schemas import SentimentArticle, SentimentResponse, SentimentRiskMetrics


def _parse_ts(s: str) -> Optional[datetime]:
    try:
        dt = dateparser.parse(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.astimezone(timezone.utc)
    except Exception:
        return None


def negative_ratio(resp: SentimentResponse) -> Optional[float]:
    total = resp.metrics.total_articles
    if total <= 0:
        return None
    return resp.metrics.negative_count / total


def dispersion(articles: List[SentimentArticle]) -> Optional[float]:
    scores = [a.score for a in articles if a.score is not None]
    if len(scores) < 3:
        return None
    return float(np.std(scores, ddof=1))


def momentum_24h_vs_7d(articles: List[SentimentArticle]) -> Optional[float]:
    now = datetime.now(timezone.utc)
    recent, prior = [], []
    for a in articles:
        ts = _parse_ts(a.published_at)
        if ts is None:
            continue
        age = now - ts
        if age <= timedelta(hours=24):
            recent.append(a.score)
        elif age <= timedelta(days=7):
            prior.append(a.score)
    if not recent or not prior:
        return None
    return float(np.mean(recent) - np.mean(prior))


def recency_weighted_sentiment(
    articles: List[SentimentArticle], half_life_hours: float = 48.0
) -> Optional[float]:
    if not articles:
        return None
    now = datetime.now(timezone.utc)
    num, den = 0.0, 0.0
    lam = np.log(2) / half_life_hours
    for a in articles:
        ts = _parse_ts(a.published_at)
        if ts is None:
            continue
        hours = max((now - ts).total_seconds() / 3600.0, 0.0)
        w = float(np.exp(-lam * hours))
        num += w * a.score
        den += w
    if den == 0:
        return None
    return num / den


def news_volume_zscore(articles: List[SentimentArticle]) -> Optional[float]:
    """Z-score of today's article count vs prior 7-day baseline."""
    now = datetime.now(timezone.utc)
    daily_counts = {}
    for a in articles:
        ts = _parse_ts(a.published_at)
        if ts is None:
            continue
        day = (now - ts).days
        if 0 <= day <= 7:
            daily_counts[day] = daily_counts.get(day, 0) + 1
    today = daily_counts.get(0, 0)
    baseline = [daily_counts.get(d, 0) for d in range(1, 8)]
    if len(baseline) < 3:
        return None
    mu = float(np.mean(baseline))
    sd = float(np.std(baseline, ddof=1))
    if sd == 0:
        return 0.0 if today == mu else (3.0 if today > mu else -3.0)
    return float((today - mu) / sd)


def source_concentration_hhi(resp: SentimentResponse) -> Optional[float]:
    breakdown = resp.metrics.sources_breakdown or {}
    total = sum(v for v in breakdown.values() if v > 0)
    if total <= 0:
        return None
    shares = [v / total for v in breakdown.values() if v > 0]
    return float(sum(s * s for s in shares))


def extreme_score_share(articles: List[SentimentArticle], threshold: float = 0.8) -> Optional[float]:
    if not articles:
        return None
    n_extreme = sum(1 for a in articles if abs(a.score) > threshold)
    return n_extreme / len(articles)


def polarity_gap(resp: SentimentResponse) -> Optional[float]:
    total = resp.metrics.total_articles
    if total <= 0:
        return None
    return abs(resp.metrics.positive_count - resp.metrics.negative_count) / total


def compute_sentiment_metrics(resp: SentimentResponse) -> SentimentRiskMetrics:
    arts = resp.articles
    disp = dispersion(arts)
    nv_z = news_volume_zscore(arts)

    vol_proxy: Optional[float]
    if disp is not None and nv_z is not None:
        vol_proxy = float(disp * max(nv_z, 0.0))
    else:
        vol_proxy = None

    return SentimentRiskMetrics(
        negative_ratio=negative_ratio(resp),
        dispersion=disp,
        momentum_24h_vs_7d=momentum_24h_vs_7d(arts),
        recency_weighted_sentiment=recency_weighted_sentiment(arts),
        news_volume_zscore=nv_z,
        source_concentration_hhi=source_concentration_hhi(resp),
        confidence=resp.confidence,
        extreme_score_share=extreme_score_share(arts),
        polarity_gap=polarity_gap(resp),
        sentiment_vol_proxy=vol_proxy,
    )
