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
    StressScenario,
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
    if market.premarket_gap_pct is not None and abs(market.premarket_gap_pct) >= 0.02:
        direction = "up" if market.premarket_gap_pct > 0 else "down"
        w.append(
            f"Significant pre-market gap {direction} ({market.premarket_gap_pct:+.1%}); "
            "elevated open-of-day volatility expected."
        )
    if market.max_drawdown is not None and market.max_drawdown < -0.4:
        w.append(f"Severe historical drawdown ({market.max_drawdown:.0%}).")
    if market.excess_kurtosis is not None and market.excess_kurtosis > 5:
        w.append("Fat-tailed return distribution (excess kurtosis > 5); VaR may understate risk.")
    if market.skew is not None and market.skew < -1:
        w.append("Strongly negative return skew; sudden large losses are historically present.")
    return w


# ---------- Assembler ----------

def _build_stress_scenarios(
    market: MarketMetrics,
    m_idx: float,
    s_idx: float,
    w_sentiment: float,
) -> List[StressScenario]:
    """Simulate portfolio impact under standard stress shocks."""
    scenarios = [
        ("mild_selloff",    -0.10),
        ("correction",      -0.20),
        ("bear_market",     -0.40),
        ("flash_crash",     -0.15),
    ]
    results = []
    for name, shock in scenarios:
        # Shocked VaR: approximate as existing VaR scaled by shock magnitude
        base_var = market.var_95_hist_1d
        new_var = round(base_var * (1 + abs(shock) * 3), 4) if base_var is not None else None
        # Shocked composite: market index worsens proportional to shock
        shocked_m_idx = min(100.0, m_idx * (1 + abs(shock) * 1.5))
        w_market = 1.0 - w_sentiment
        new_comp = round(composite.composite_score(shocked_m_idx, s_idx, w_market, w_sentiment), 2)
        results.append(StressScenario(
            name=name,
            shock_pct=shock,
            new_var_95=new_var,
            new_composite_score=new_comp,
        ))
    return results


def build_report(
    req: RiskRequest,
    market: MarketMetrics,
    sentiment: SentimentRiskMetrics,
    s_resp: SentimentResponse,
    price_data_as_of: str,
    sentiment_fetched_at: str,
) -> RiskResponse:
    m_idx, s_idx = composite.compute_indices(market, sentiment)

    # C2: Dynamic sentiment weight — scale by article count + confidence
    dyn_w_sentiment = composite.dynamic_sentiment_weight(
        total_articles=s_resp.metrics.total_articles,
        confidence=float(s_resp.confidence),
        base_weight=req.weights.sentiment,
    )
    dyn_w_market = 1.0 - dyn_w_sentiment
    comp = composite.composite_score(m_idx, s_idx, dyn_w_market, dyn_w_sentiment)

    stop_pct = _suggested_stop_loss(market.atr14_pct)
    kelly = _kelly_fraction_capped(market.vol_ann_1y, market.sharpe)
    size_pct, size_usd = _position_size(req.account_size, req.max_risk_pct, stop_pct)

    recs = Recommendations(
        suggested_stop_loss_pct=stop_pct,
        kelly_fraction_capped=kelly,
        position_size_pct_of_account=size_pct,
        position_size_usd=size_usd,
    )

    stress = _build_stress_scenarios(market, m_idx, s_idx, dyn_w_sentiment)

    return RiskResponse(
        ticker=req.ticker,
        as_of=datetime.now(timezone.utc).date().isoformat(),
        composite_risk_score=round(comp, 2),
        risk_bucket=composite.bucket(comp),
        market_risk=MarketRiskBlock(index=round(m_idx, 2), metrics=market),
        sentiment_risk=SentimentRiskBlock(index=round(s_idx, 2), metrics=sentiment),
        recommendations=recs,
        stress_scenarios=stress,
        warnings=_build_warnings(market, sentiment, s_resp),
        meta=Meta(
            sentiment_fetched_at=sentiment_fetched_at,
            price_data_as_of=price_data_as_of,
            benchmark=req.benchmark,
            lookback_days=req.lookback_days,
            weights={"market": round(dyn_w_market, 3), "sentiment": round(dyn_w_sentiment, 3)},
        ),
    )
