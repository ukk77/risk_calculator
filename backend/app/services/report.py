"""Assemble the final RiskResponse."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from ..models.schemas import (
    MarketMetrics,
    MarketRiskBlock,
    Meta,
    Recommendations,
    RiskRequest,
    RiskResponse,
    SentimentResponse,
    SentimentRiskBlock,
    SentimentRiskMetrics,
)
from . import composite


# ---------- Derived recommendations ----------

def _suggested_stop_loss(atr_pct: Optional[float], k: float = 2.0) -> Optional[float]:
    if atr_pct is None:
        return None
    return float(-k * atr_pct)


def _kelly_fraction_capped(
    vol_ann: Optional[float],
    sharpe: Optional[float],
    cap: float = 0.25,
) -> Optional[float]:
    if vol_ann is None or sharpe is None or vol_ann <= 0:
        return None
    # Kelly ~ mean / variance; using Sharpe as proxy: mean/sigma_ann = sharpe
    # -> Kelly_ann = sharpe / sigma_ann
    raw = sharpe / vol_ann
    return float(max(0.0, min(raw, cap)))


def _position_size(
    account: Optional[float],
    max_risk_pct: Optional[float],
    stop_pct: Optional[float],
) -> (Optional[float], Optional[float]):
    if account is None or max_risk_pct is None or stop_pct is None or stop_pct == 0:
        return None, None
    risk_usd = account * (max_risk_pct / 100.0)
    # stop_pct is negative; size = risk_usd / |stop_pct|
    size_usd = risk_usd / abs(stop_pct)
    size_pct = size_usd / account * 100.0
    return float(min(size_pct, 100.0)), float(min(size_usd, account))


# ---------- Warnings ----------

def _build_warnings(
    market: MarketMetrics, sentiment: SentimentRiskMetrics, s_resp: SentimentResponse
) -> List[str]:
    w: List[str] = []
    if sentiment.source_concentration_hhi is not None and sentiment.source_concentration_hhi > 0.6:
        # Identify dominant source for the message.
        breakdown = s_resp.metrics.sources_breakdown or {}
        total = sum(breakdown.values())
        if total > 0:
            dom = max(breakdown.items(), key=lambda kv: kv[1])
            pct = 100.0 * dom[1] / total
            w.append(f"High source concentration: {pct:.0f}% of articles from '{dom[0]}'.")
    if s_resp.metrics.total_articles < 20:
        w.append(f"Low news volume ({s_resp.metrics.total_articles} articles); sentiment metrics may be unreliable.")
    if sentiment.confidence is not None and sentiment.confidence < 0.5:
        w.append(f"Low sentiment confidence ({sentiment.confidence:.2f}).")
    if market.max_drawdown is not None and market.max_drawdown < -0.4:
        w.append(f"Severe historical drawdown ({market.max_drawdown:.0%}).")
    if market.excess_kurtosis is not None and market.excess_kurtosis > 5:
        w.append("Fat-tailed return distribution (excess kurtosis > 5); VaR may understate risk.")
    if market.skew is not None and market.skew < -1:
        w.append("Strongly negative return skew; sudden large losses are historically present.")
    return w


# ---------- Assembler ----------

def build_report(
    req: RiskRequest,
    market: MarketMetrics,
    sentiment: SentimentRiskMetrics,
    s_resp: SentimentResponse,
    price_data_as_of: str,
    sentiment_fetched_at: str,
) -> RiskResponse:
    m_idx, s_idx = composite.compute_indices(market, sentiment)
    comp = composite.composite_score(m_idx, s_idx, req.weights.market, req.weights.sentiment)

    stop_pct = _suggested_stop_loss(market.atr14_pct)
    kelly = _kelly_fraction_capped(market.vol_ann_1y, market.sharpe)
    size_pct, size_usd = _position_size(req.account_size, req.max_risk_pct, stop_pct)

    recs = Recommendations(
        suggested_stop_loss_pct=stop_pct,
        kelly_fraction_capped=kelly,
        position_size_pct_of_account=size_pct,
        position_size_usd=size_usd,
    )

    return RiskResponse(
        ticker=req.ticker,
        as_of=datetime.now(timezone.utc).date().isoformat(),
        composite_risk_score=round(comp, 2),
        risk_bucket=composite.bucket(comp),
        market_risk=MarketRiskBlock(index=round(m_idx, 2), metrics=market),
        sentiment_risk=SentimentRiskBlock(index=round(s_idx, 2), metrics=sentiment),
        recommendations=recs,
        warnings=_build_warnings(market, sentiment, s_resp),
        meta=Meta(
            sentiment_fetched_at=sentiment_fetched_at,
            price_data_as_of=price_data_as_of,
            benchmark=req.benchmark,
            lookback_days=req.lookback_days,
            weights={"market": req.weights.market, "sentiment": req.weights.sentiment},
        ),
    )
