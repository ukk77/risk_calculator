"""FastAPI entry point for risk_calculator."""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException

from .models.schemas import RiskRequest, RiskResponse
from .services import db as risk_db
from .services import market_data, risk_metrics, sentiment_client, sentiment_risk
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
    m_metrics = risk_metrics.compute_market_metrics(ohlc, bench, rf_annual=rf)
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
