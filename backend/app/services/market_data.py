"""Historical price data fetch from the centralized Parquet Data Lake."""
from __future__ import annotations

import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Optional

import pandas as pd
import yfinance as yf

BASE_DIR = Path(__file__).resolve().parents[4] # risk_calculator/backend/app/services/market_data.py -> trading/
MARKET_DATA_DIR = BASE_DIR / "market_data"

def fetch_ohlcv(ticker: str, lookback_days: int = 504, interval: str = "1d") -> pd.DataFrame:
    """Return OHLCV indexed by date (UTC-naive). Reads from local Parquet cache."""
    if interval == "1d":
        parquet_path = MARKET_DATA_DIR / "daily" / f"{ticker}.parquet"
    elif interval == "1h":
        parquet_path = MARKET_DATA_DIR / "hourly" / f"{ticker}.parquet"
    else:
        raise ValueError(f"Unsupported interval: {interval}")

    if not parquet_path.exists():
        raise RuntimeError(f"No cached data found for '{ticker}' at {parquet_path}. Run data_ingestion.py first.")

    df = pd.read_parquet(parquet_path)
    
    # Filter by lookback_days
    # Polygon data is in UTC.
    end = datetime.now(timezone.utc)
    start = end - timedelta(days=lookback_days)
    
    # Ensure index is datetime and tz-aware for comparison, then slice
    if df.index.tz is None:
        df.index = df.index.tz_localize("UTC")
        
    df = df.loc[start:end].copy()
    
    # Make timezone naive to match original yfinance behavior
    df.index = df.index.tz_localize(None)
    
    # Map lowercase Polygon columns to TitleCase expected by the strategies
    rename_map = {
        "open": "Open", 
        "high": "High", 
        "low": "Low", 
        "close": "Close", 
        "volume": "Volume"
    }
    df = df.rename(columns=rename_map)
    
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
