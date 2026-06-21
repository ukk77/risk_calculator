"""Market-based risk sub-metrics.

All functions accept a pandas Series/DataFrame and return plain floats (or None
when insufficient data). Returns-based metrics use log returns unless noted.
"""
from __future__ import annotations

from typing import Optional, Tuple

import numpy as np
import pandas as pd
from scipy import stats

from ..models.schemas import MarketMetrics
from ..utils.stats import TRADING_DAYS, annualize_vol, log_returns


# ---------- Volatility family ----------

def rolling_vol_annual(returns: pd.Series, window: int) -> Optional[float]:
    if len(returns) < window:
        return None
    tail = returns.tail(window)
    return float(tail.std(ddof=1) * np.sqrt(TRADING_DAYS))


def downside_deviation_annual(returns: pd.Series, mar: float = 0.0) -> Optional[float]:
    if returns.empty:
        return None
    downside = returns[returns < mar]
    if downside.empty:
        return 0.0
    return float(downside.std(ddof=1) * np.sqrt(TRADING_DAYS))


# ---------- VaR / CVaR ----------

def historical_var(returns: pd.Series, alpha: float) -> Optional[float]:
    if returns.empty:
        return None
    return float(np.quantile(returns, 1 - alpha))


def parametric_var(returns: pd.Series, alpha: float) -> Optional[float]:
    if returns.empty:
        return None
    mu, sigma = float(returns.mean()), float(returns.std(ddof=1))
    z = stats.norm.ppf(1 - alpha)
    return float(mu + sigma * z)


def conditional_var(returns: pd.Series, alpha: float) -> Optional[float]:
    if returns.empty:
        return None
    q = np.quantile(returns, 1 - alpha)
    tail = returns[returns <= q]
    if tail.empty:
        return float(q)
    return float(tail.mean())


# ---------- Drawdown ----------

def max_drawdown(prices: pd.Series) -> Tuple[Optional[float], Optional[int]]:
    if prices.empty:
        return None, None
    cummax = prices.cummax()
    dd = prices / cummax - 1.0
    mdd = float(dd.min())
    # Duration: longest run where price is below a running peak.
    below = (prices < cummax).astype(int)
    # Length of the longest streak of 1s
    longest = 0
    cur = 0
    for v in below.values:
        if v:
            cur += 1
            longest = max(longest, cur)
        else:
            cur = 0
    return mdd, int(longest)


# ---------- Beta / ratios ----------

def beta(asset_returns: pd.Series, bench_returns: pd.Series) -> Optional[float]:
    joined = pd.concat([asset_returns, bench_returns], axis=1, join="inner").dropna()
    if len(joined) < 30:
        return None
    a, b = joined.iloc[:, 0], joined.iloc[:, 1]
    var_b = float(b.var(ddof=1))
    if var_b == 0:
        return None
    return float(np.cov(a, b, ddof=1)[0, 1] / var_b)


def sharpe_ratio(returns: pd.Series, rf_annual: float) -> Optional[float]:
    if returns.empty:
        return None
    rf_daily = rf_annual / TRADING_DAYS
    excess = returns - rf_daily
    sd = float(excess.std(ddof=1))
    if sd == 0:
        return None
    return float(excess.mean() / sd * np.sqrt(TRADING_DAYS))


def sortino_ratio(returns: pd.Series, rf_annual: float) -> Optional[float]:
    if returns.empty:
        return None
    rf_daily = rf_annual / TRADING_DAYS
    excess = returns - rf_daily
    downside = excess[excess < 0]
    if downside.empty:
        return None
    dd = float(downside.std(ddof=1))
    if dd == 0:
        return None
    return float(excess.mean() / dd * np.sqrt(TRADING_DAYS))


# ---------- Distribution shape ----------

def skewness(returns: pd.Series) -> Optional[float]:
    if len(returns) < 3:
        return None
    return float(stats.skew(returns, bias=False))


def excess_kurtosis(returns: pd.Series) -> Optional[float]:
    if len(returns) < 4:
        return None
    return float(stats.kurtosis(returns, fisher=True, bias=False))


# ---------- ATR / gap / liquidity / range ----------

def atr14_pct(ohlc: pd.DataFrame, period: int = 14) -> Optional[float]:
    if len(ohlc) < period + 1:
        return None
    high, low, close = ohlc["High"], ohlc["Low"], ohlc["Close"]
    prev_close = close.shift(1)
    tr = pd.concat(
        [(high - low), (high - prev_close).abs(), (low - prev_close).abs()],
        axis=1,
    ).max(axis=1)
    atr = tr.rolling(period).mean().iloc[-1]
    last_close = float(close.iloc[-1])
    if last_close == 0 or pd.isna(atr):
        return None
    return float(atr / last_close)


def gap_risk_frequency(ohlc: pd.DataFrame, sigma_mult: float = 2.0) -> Optional[float]:
    """Fraction of overnight gaps whose magnitude exceeds sigma_mult * realized daily sigma."""
    if len(ohlc) < 30:
        return None
    prev_close = ohlc["Close"].shift(1)
    gap = (ohlc["Open"] - prev_close) / prev_close
    gap = gap.dropna()
    if gap.empty:
        return None
    sigma = float(gap.std(ddof=1))
    if sigma == 0:
        return 0.0
    big = (gap.abs() > sigma_mult * sigma).sum()
    return float(big / len(gap))


def premarket_gap_pct(ticker: str) -> Optional[float]:
    """Signed pre-market gap for today: (first pre-market open - prior regular close) / prior close.

    Uses fetch_ohlcv_extended to access extended-hours hourly bars. Returns None when
    there are no pre-market bars for the current trading day or the cache is unavailable.
    """
    try:
        from .market_data import fetch_ohlcv_extended
        df = fetch_ohlcv_extended(ticker, lookback_days=5)
    except Exception:
        return None

    if df.empty:
        return None

    today = pd.Timestamp.now().normalize()

    regular_closes = df[~df["is_extended"]]["Close"].dropna()
    premarket_bars = df[
        df["is_extended"] & (pd.to_datetime(df.index).normalize() == today)
    ]

    if premarket_bars.empty or regular_closes.empty:
        return None

    prior_close = float(regular_closes.iloc[-1])
    if prior_close == 0:
        return None

    first_pm_open = float(premarket_bars["Open"].iloc[0])
    return float((first_pm_open - prior_close) / prior_close)


def liquidity_score(ohlc: pd.DataFrame) -> Optional[float]:
    """0-100 score: higher = more liquid. Based on avg dollar volume and zero-volume share."""
    if ohlc.empty:
        return None
    dollar_vol = (ohlc["Close"] * ohlc["Volume"]).dropna()
    if dollar_vol.empty:
        return None
    avg_dv = float(dollar_vol.tail(60).mean())
    zero_share = float((ohlc["Volume"] == 0).mean())
    # Log-scale: $1M/day ~ 40, $100M/day ~ 70, $1B/day ~ 90, $10B+/day ~ 100.
    score = 10.0 * np.log10(max(avg_dv, 1.0))
    score = float(np.clip(score, 0, 100))
    score *= (1.0 - zero_share)
    return float(np.clip(score, 0, 100))


def range_52w_position(prices: pd.Series) -> Optional[float]:
    tail = prices.tail(252)
    if len(tail) < 30:
        return None
    lo, hi = float(tail.min()), float(tail.max())
    if hi == lo:
        return 0.5
    return float((tail.iloc[-1] - lo) / (hi - lo))


# ---------- Aggregator ----------

def compute_market_metrics(
    ohlc: pd.DataFrame,
    bench_ohlc: pd.DataFrame,
    rf_annual: float,
    ticker: Optional[str] = None,
) -> MarketMetrics:
    close = ohlc["Close"]
    rets = log_returns(close)
    bench_rets = log_returns(bench_ohlc["Close"]) if not bench_ohlc.empty else pd.Series(dtype=float)

    mdd, mdd_dur = max_drawdown(close)

    return MarketMetrics(
        vol_ann_30d=rolling_vol_annual(rets, 30),
        vol_ann_90d=rolling_vol_annual(rets, 90),
        vol_ann_1y=rolling_vol_annual(rets, 252) or annualize_vol(rets),
        downside_deviation_ann=downside_deviation_annual(rets),
        var_95_hist_1d=historical_var(rets, 0.95),
        var_99_hist_1d=historical_var(rets, 0.99),
        var_95_param_1d=parametric_var(rets, 0.95),
        var_99_param_1d=parametric_var(rets, 0.99),
        cvar_95_1d=conditional_var(rets, 0.95),
        max_drawdown=mdd,
        max_drawdown_duration_days=mdd_dur,
        beta=beta(rets, bench_rets),
        sharpe=sharpe_ratio(rets, rf_annual),
        sortino=sortino_ratio(rets, rf_annual),
        skew=skewness(rets),
        excess_kurtosis=excess_kurtosis(rets),
        atr14_pct=atr14_pct(ohlc),
        gap_risk_freq=gap_risk_frequency(ohlc),
        premarket_gap_pct=premarket_gap_pct(ticker) if ticker else None,
        liquidity_score=liquidity_score(ohlc),
        range_52w_position=range_52w_position(close),
    )
