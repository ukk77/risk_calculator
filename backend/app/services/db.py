"""SQLite-based historical risk tracking.

Mirrors sentiment_analysis/backend/app/services/db.py. Zero-config file-based
storage using Python stdlib sqlite3.

DB file: backend/risk_history.db  (auto-created on first use; add to .gitignore)

One row per (ticker, captured_at) storing:
  - Composite risk score + bucket
  - Market-risk sub-metrics (MarketMetrics)
  - Sentiment-risk sub-metrics (SentimentRiskMetrics)
  - Upstream sentiment summary (overall, confidence, total_articles)
"""
from __future__ import annotations

import json
import os
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

_DEFAULT_DB = Path(__file__).resolve().parents[2] / "risk_history.db"
DB_PATH = Path(os.environ.get("RISK_DB_PATH", str(_DEFAULT_DB)))


# ---------- Column definitions (keep in sync with schemas.MarketMetrics / SentimentRiskMetrics) ----------

MARKET_COLS: List[str] = [
    "vol_ann_30d",
    "vol_ann_90d",
    "vol_ann_1y",
    "downside_deviation_ann",
    "var_95_hist_1d",
    "var_99_hist_1d",
    "var_95_param_1d",
    "var_99_param_1d",
    "cvar_95_1d",
    "max_drawdown",
    "max_drawdown_duration_days",
    "beta",
    "sharpe",
    "sortino",
    "skew",
    "excess_kurtosis",
    "atr14_pct",
    "gap_risk_freq",
    "liquidity_score",
    "range_52w_position",
]

SENTIMENT_COLS: List[str] = [
    "negative_ratio",
    "dispersion",
    "momentum_24h_vs_7d",
    "recency_weighted_sentiment",
    "news_volume_zscore",
    "source_concentration_hhi",
    "sentiment_confidence",        # stored as sentiment_confidence to avoid collision
    "extreme_score_share",
    "polarity_gap",
    "sentiment_vol_proxy",
]


def _get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    return conn


def init_db() -> None:
    """Create the risk_snapshots table and index if they don't exist."""
    cols_sql = [
        "id                        INTEGER PRIMARY KEY AUTOINCREMENT",
        "ticker                    TEXT    NOT NULL",
        "captured_at               TEXT    NOT NULL",
        "as_of                     TEXT    NOT NULL",
        "composite_risk_score      REAL    NOT NULL",
        "risk_bucket               TEXT    NOT NULL",
        "market_index              REAL    NOT NULL",
        "sentiment_index           REAL    NOT NULL",
        # Upstream sentiment summary
        "overall_sentiment         TEXT",
        "upstream_confidence       REAL",
        "total_articles            INTEGER",
        # Recommendations
        "suggested_stop_loss_pct       REAL",
        "kelly_fraction_capped         REAL",
        "position_size_pct_of_account  REAL",
        "position_size_usd             REAL",
        # Warnings serialized as JSON
        "warnings_json             TEXT",
        "benchmark                 TEXT",
        "lookback_days             INTEGER",
        "weight_market             REAL",
        "weight_sentiment          REAL",
    ]
    for c in MARKET_COLS:
        cols_sql.append(f"{c} REAL")
    for c in SENTIMENT_COLS:
        cols_sql.append(f"{c} REAL")

    create_sql = "CREATE TABLE IF NOT EXISTS risk_snapshots (\n  " + ",\n  ".join(cols_sql) + "\n)"

    with _get_conn() as conn:
        conn.execute(create_sql)
        conn.execute(
            "CREATE INDEX IF NOT EXISTS idx_risk_ticker_date "
            "ON risk_snapshots(ticker, captured_at)"
        )
        conn.commit()
        try:
            conn.execute("ALTER TABLE risk_snapshots ADD COLUMN session TEXT")
            conn.commit()
        except Exception:
            pass  # column already exists


def save_snapshot(report: Dict[str, Any], session: str = "intraday") -> None:
    """Persist one RiskResponse (as a dict) to the DB.

    Expects the dict form of the RiskResponse pydantic model.
    """
    init_db()
    captured_at = datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")

    market_metrics = (report.get("market_risk") or {}).get("metrics") or {}
    sent_metrics_raw = (report.get("sentiment_risk") or {}).get("metrics") or {}
    # Map pydantic field `confidence` -> DB column `sentiment_confidence`
    sent_metrics = dict(sent_metrics_raw)
    if "confidence" in sent_metrics:
        sent_metrics["sentiment_confidence"] = sent_metrics.pop("confidence")

    recs = report.get("recommendations") or {}
    meta = report.get("meta") or {}
    weights = meta.get("weights") or {}

    row: Dict[str, Any] = {
        "ticker":               report.get("ticker", "").upper(),
        "captured_at":          captured_at,
        "as_of":                report.get("as_of") or captured_at[:10],
        "composite_risk_score": float(report.get("composite_risk_score") or 0.0),
        "risk_bucket":          report.get("risk_bucket") or "moderate",
        "market_index":         float((report.get("market_risk") or {}).get("index") or 0.0),
        "sentiment_index":      float((report.get("sentiment_risk") or {}).get("index") or 0.0),
        "overall_sentiment":    (report.get("_sentiment_summary") or {}).get("overall_sentiment"),
        "upstream_confidence":  (report.get("_sentiment_summary") or {}).get("confidence"),
        "total_articles":       (report.get("_sentiment_summary") or {}).get("total_articles"),
        "suggested_stop_loss_pct":      recs.get("suggested_stop_loss_pct"),
        "kelly_fraction_capped":        recs.get("kelly_fraction_capped"),
        "position_size_pct_of_account": recs.get("position_size_pct_of_account"),
        "position_size_usd":            recs.get("position_size_usd"),
        "warnings_json":        json.dumps(report.get("warnings") or []),
        "benchmark":            meta.get("benchmark"),
        "lookback_days":        meta.get("lookback_days"),
        "weight_market":        weights.get("market"),
        "weight_sentiment":     weights.get("sentiment"),
        "session":              session,
    }
    for c in MARKET_COLS:
        row[c] = market_metrics.get(c)
    for c in SENTIMENT_COLS:
        row[c] = sent_metrics.get(c)

    cols = list(row.keys())
    placeholders = ",".join(["?"] * len(cols))
    sql = f"INSERT INTO risk_snapshots ({','.join(cols)}) VALUES ({placeholders})"
    with _get_conn() as conn:
        conn.execute(sql, [row[c] for c in cols])
        conn.commit()


def get_history(ticker: str, limit: int = 90) -> List[Dict[str, Any]]:
    """Return the last *limit* snapshots for *ticker*, newest first."""
    init_db()
    with _get_conn() as conn:
        rows = conn.execute(
            "SELECT * FROM risk_snapshots "
            "WHERE UPPER(ticker) = UPPER(?) "
            "ORDER BY captured_at DESC LIMIT ?",
            (ticker.upper(), limit),
        ).fetchall()
    out: List[Dict[str, Any]] = []
    for row in rows:
        d = dict(row)
        try:
            d["warnings"] = json.loads(d.pop("warnings_json") or "[]")
        except Exception:
            d["warnings"] = []
        out.append(d)
    return out
