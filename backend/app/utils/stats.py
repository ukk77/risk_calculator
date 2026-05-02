"""Small statistical helpers."""
from __future__ import annotations

from typing import Optional

import numpy as np
import pandas as pd


TRADING_DAYS = 252


def log_returns(prices: pd.Series) -> pd.Series:
    return np.log(prices / prices.shift(1)).dropna()


def annualize_vol(daily_returns: pd.Series) -> Optional[float]:
    if daily_returns.empty:
        return None
    return float(daily_returns.std(ddof=1) * np.sqrt(TRADING_DAYS))


def clip01(x: float) -> float:
    return float(max(0.0, min(1.0, x)))


def piecewise_score(value: float, low: float, high: float) -> float:
    """Map a raw value to 0-100 risk contribution, linear between thresholds.

    value <= low -> 0, value >= high -> 100.
    """
    if value is None or np.isnan(value):
        return 50.0
    if high == low:
        return 50.0
    t = (value - low) / (high - low)
    return 100.0 * clip01(t)
