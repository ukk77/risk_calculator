"""FastAPI entry point for risk_calculator."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException

from .models.schemas import (
    RiskRequest, RiskResponse,
    PortfolioRiskRequest, PortfolioRiskResponse, PortfolioTickerRisk,
)
from .services import db as risk_db
from .services import market_data, risk_metrics, sentiment_client, sentiment_risk
from .services import composite as composite_svc
from .services.report import build_report


app = FastAPI(
    title="Risk Calculator",
    version="0.1.0",
    description="Computes a full risk report combining market data (yfinance) and "
                "sentiment data (sentiment_analysis API).",
)


@app.get("/api/health")
def health():
    upstream_ok = sentiment_client.check_health()
    return {
        "status": "ok",
        "sentiment_analysis_reachable": upstream_ok,
        "sentiment_analysis_url": sentiment_client.DEFAULT_BASE_URL,
    }


@app.post("/api/risk", response_model=RiskResponse)
def risk(req: RiskRequest) -> RiskResponse:
    base_url = req.sentiment_api_url or sentiment_client.DEFAULT_BASE_URL

    # 1. Sentiment (upstream).
    try:
        s_resp = sentiment_client.fetch_sentiment(
            ticker=req.ticker,
            company_name=req.company_name or req.ticker,
            base_url=base_url,
        )
    except sentiment_client.SentimentServiceDownError as e:
        raise HTTPException(
            status_code=503,
            detail={
                "error": "sentiment_analysis_unreachable",
                "base_url": e.base_url,
                "detail": e.detail,
                "remediation": "Start the sentiment_analysis backend: "
                               "cd sentiment_analysis/backend && python -m app.main",
            },
        )
    except sentiment_client.SentimentContractError as e:
        raise HTTPException(status_code=502, detail={"error": "contract_violation", "message": str(e)})

    sentiment_fetched_at = datetime.now(timezone.utc).isoformat()

    # 2. Market data.
    try:
        ohlc = market_data.fetch_ohlcv(req.ticker, req.lookback_days)
        bench = market_data.fetch_ohlcv(req.benchmark, req.lookback_days)
    except Exception as e:
        raise HTTPException(status_code=502, detail={"error": "market_data_failed", "message": str(e)})

    rf = market_data.fetch_risk_free_rate_annual()
    price_as_of = ohlc.index[-1].date().isoformat()

    # 3. Metrics.
    m_metrics = risk_metrics.compute_market_metrics(ohlc, bench, rf_annual=rf, ticker=req.ticker)
    s_metrics = sentiment_risk.compute_sentiment_metrics(s_resp)

    # 4. Report.
    report = build_report(
        req=req,
        market=m_metrics,
        sentiment=s_metrics,
        s_resp=s_resp,
        price_data_as_of=price_as_of,
        sentiment_fetched_at=sentiment_fetched_at,
    )

    # 5. Persist historical snapshot (best-effort, non-fatal).
    try:
        report_dict = report.model_dump()
        report_dict["_sentiment_summary"] = {
            "overall_sentiment": s_resp.overall_sentiment,
            "confidence":        s_resp.confidence,
            "total_articles":    s_resp.metrics.total_articles,
        }
        risk_db.save_snapshot(report_dict)
    except Exception as exc:
        print(f"[risk_calculator] Failed to save history snapshot: {exc}")

    return report


@app.post("/api/risk/portfolio", response_model=PortfolioRiskResponse)
def portfolio_risk(req: PortfolioRiskRequest) -> PortfolioRiskResponse:
    """Multi-ticker portfolio risk endpoint.

    Computes a composite risk score for each holding, weights them by position
    size, and returns portfolio-level metrics including concentration (HHI) and
    a pairwise-correlation diversification ratio.

    - **holdings**: list of {ticker, weight} pairs (weights should sum to ~1.0)
    - **benchmark**: benchmark ticker for beta calculation (default: SPY)
    - **lookback_days**: history window (default: 252)
    """
    if not req.holdings:
        raise HTTPException(status_code=422, detail="holdings list must not be empty")

    base_url = req.sentiment_api_url or sentiment_client.DEFAULT_BASE_URL
    ticker_results: list[PortfolioTickerRisk] = []
    warnings: list[str] = []
    returns_map: dict[str, object] = {}   # ticker -> pd.Series for correlation

    for holding in req.holdings:
        t = holding.ticker.upper()
        try:
            s_resp = sentiment_client.fetch_sentiment(
                ticker=t, company_name=t, base_url=base_url,
            )
        except Exception:
            s_resp = None

        try:
            ohlc = market_data.fetch_ohlcv(t, req.lookback_days)
            bench = market_data.fetch_ohlcv(req.benchmark, req.lookback_days)
            rf = market_data.fetch_risk_free_rate_annual()
            m_metrics = risk_metrics.compute_market_metrics(ohlc, bench, rf_annual=rf, ticker=t)
            returns_map[t] = ohlc["close"].pct_change().dropna()
        except Exception as exc:
            warnings.append(f"{t}: market data failed — {exc}")
            continue

        if s_resp is not None:
            s_metrics = sentiment_risk.compute_sentiment_metrics(s_resp)
        else:
            from .models.schemas import SentimentRiskMetrics
            s_metrics = SentimentRiskMetrics()
            warnings.append(f"{t}: sentiment unavailable, using zero sentiment contribution")

        m_idx, s_idx = composite_svc.compute_indices(m_metrics, s_metrics)
        dyn_w_s = composite_svc.dynamic_sentiment_weight(
            total_articles=s_resp.metrics.total_articles if s_resp else 0,
            confidence=float(s_resp.confidence) if s_resp else 0.0,
        )
        comp = composite_svc.composite_score(m_idx, s_idx, 1.0 - dyn_w_s, dyn_w_s)
        rbucket = composite_svc.bucket(comp)

        ticker_results.append(PortfolioTickerRisk(
            ticker=t,
            weight=holding.weight,
            composite_risk_score=round(comp, 2),
            risk_bucket=rbucket,
            weighted_contribution=round(comp * holding.weight, 3),
        ))

    if not ticker_results:
        raise HTTPException(status_code=502, detail="Could not compute risk for any holding")

    # Portfolio composite = weighted sum of individual scores
    total_weight = sum(r.weight for r in ticker_results)
    port_score = sum(r.weighted_contribution for r in ticker_results) / total_weight if total_weight else 50.0

    # Concentration HHI = sum(weight^2)
    hhi = sum(r.weight ** 2 for r in ticker_results)

    # Pairwise correlation → diversification ratio
    diversification_ratio: float | None = None
    try:
        import pandas as pd
        tickers_with_returns = [r.ticker for r in ticker_results if r.ticker in returns_map]
        if len(tickers_with_returns) >= 2:
            ret_df = pd.concat(
                {t: returns_map[t] for t in tickers_with_returns}, axis=1
            ).dropna()
            corr_matrix = ret_df.corr()
            n = len(tickers_with_returns)
            pairs = [(i, j) for i in range(n) for j in range(i + 1, n)]
            avg_corr = sum(
                corr_matrix.iloc[i, j] for i, j in pairs
            ) / len(pairs) if pairs else 0.0
            diversification_ratio = round(1.0 - float(avg_corr), 3)
            # Annotate per-ticker correlation to portfolio
            port_weights = {r.ticker: r.weight for r in ticker_results}
            for r in ticker_results:
                if r.ticker in returns_map and tickers_with_returns:
                    others = [t for t in tickers_with_returns if t != r.ticker]
                    if others:
                        w_sum = sum(port_weights.get(t, 0) for t in others)
                        corr_to_port = sum(
                            corr_matrix.loc[r.ticker, t] * port_weights.get(t, 0)
                            for t in others
                        ) / w_sum if w_sum else None
                        r.correlation_to_portfolio = round(float(corr_to_port), 3) if corr_to_port is not None else None
    except Exception as exc:
        warnings.append(f"Correlation computation failed: {exc}")

    if total_weight < 0.99 or total_weight > 1.01:
        warnings.append(f"Holdings weights sum to {total_weight:.3f} (expected 1.0); scores are weight-normalised.")

    return PortfolioRiskResponse(
        as_of=datetime.now(timezone.utc).date().isoformat(),
        portfolio_composite_score=round(port_score, 2),
        portfolio_risk_bucket=composite_svc.bucket(port_score),
        diversification_ratio=diversification_ratio,
        concentration_hhi=round(hhi, 4),
        tickers=ticker_results,
        warnings=warnings,
    )


@app.get("/api/history/{ticker}")
def get_risk_history(ticker: str, limit: int = 90):
    """Return historical risk snapshots for a ticker (newest first).

    Each snapshot is one completed ``POST /api/risk`` call (or a row written
    by ``backend/run_daily_risk.py``) stored in ``backend/risk_history.db``.
    """
    try:
        rows = risk_db.get_history(ticker.upper(), limit=min(max(limit, 1), 365))
        return {"ticker": ticker.upper(), "count": len(rows), "snapshots": rows}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=f"Error fetching history: {exc}")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=8100, reload=False)
