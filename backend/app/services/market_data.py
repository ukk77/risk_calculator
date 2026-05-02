"""Historical price data fetch (yfinance) with simple on-disk cache."""
from __future__ import annotations

import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf

CACHE_DIR = Path(os.path.expanduser("~")) / ".risk_calculator_cache"
CACHE_DIR.mkdir(parents=True, exist_ok=True)
CACHE_TTL_HOURS = 6


def _cache_path(ticker: str, lookback_days: int) -> Path:
    safe = ticker.replace("/", "_").replace("\\", "_")
    return CACHE_DIR / f"{safe}_{lookback_days}.parquet"


def _fresh(path: Path) -> bool:
    if not path.exists():
        return False
    age = datetime.utcnow() - datetime.utcfromtimestamp(path.stat().st_mtime)
    return age < timedelta(hours=CACHE_TTL_HOURS)


def fetch_ohlcv(ticker: str, lookback_days: int = 504) -> pd.DataFrame:
    """Return daily OHLCV indexed by date (UTC-naive). Uses parquet cache."""
    path = _cache_path(ticker, lookback_days)
    if _fresh(path):
        try:
            return pd.read_parquet(path)
        except Exception:
            pass

    end = datetime.utcnow()
    start = end - timedelta(days=lookback_days)
    df = yf.download(
        ticker,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        progress=False,
        auto_adjust=True,
        threads=False,
    )
    if df is None or df.empty:
        raise RuntimeError(f"No price data returned from yfinance for '{ticker}'.")

    # Flatten multiindex if present (yfinance sometimes returns (field, ticker) cols)
    if isinstance(df.columns, pd.MultiIndex):
        df.columns = [c[0] for c in df.columns]
    df.index = pd.to_datetime(df.index).tz_localize(None)
    df = df[["Open", "High", "Low", "Close", "Volume"]].dropna()

    try:
        df.to_parquet(path)
    except Exception:
        pass
    return df


def fetch_risk_free_rate_annual(default: float = 0.04) -> float:
    """Return annualized risk-free rate proxy (^IRX is quoted as % annualized)."""
    try:
        df = yf.download("^IRX", period="1mo", progress=False, threads=False)
        if df is None or df.empty:
            return default
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [c[0] for c in df.columns]
        last = float(df["Close"].dropna().iloc[-1])
        return last / 100.0
    except Exception:
        return default
