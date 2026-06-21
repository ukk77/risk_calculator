"""Pydantic models matching the JSON Schemas in contracts/."""
from __future__ import annotations

from typing import Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


# --- Sentiment upstream new models (added with features v2) ---

class TopicKeyword(BaseModel):
    model_config = ConfigDict(extra="allow")
    keyword: str
    count: int
    avg_sentiment: float


class AnalystRatings(BaseModel):
    model_config = ConfigDict(extra="allow")
    recommendation: str = ""
    target_mean_price: Optional[float] = None
    target_high_price: Optional[float] = None
    target_low_price:  Optional[float] = None
    num_analysts:  int = 0
    strong_buy:    int = 0
    buy:           int = 0
    hold:          int = 0
    sell:          int = 0
    strong_sell:   int = 0


class LeadLagPoint(BaseModel):
    model_config = ConfigDict(extra="allow")
    offset_days: int
    correlation: float


class PriceCorrelation(BaseModel):
    model_config = ConfigDict(extra="allow")
    pearson_r:            Optional[float] = None
    divergence_alert:     bool = False
    divergence_direction: Optional[str] = None
    lead_lag:             List[LeadLagPoint] = Field(default_factory=list)


# --- Request / client-facing ---

class Weights(BaseModel):
    model_config = ConfigDict(extra="forbid")
    market: float = 0.7
    sentiment: float = 0.3


class RiskRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticker: str = Field(..., pattern=r"^[A-Z][A-Z0-9.\-]{0,9}$")
    company_name: Optional[str] = None
    lookback_days: int = Field(504, ge=60, le=3650)
    benchmark: str = "SPY"
    weights: Weights = Field(default_factory=Weights)
    account_size: Optional[float] = Field(None, gt=0)
    max_risk_pct: Optional[float] = Field(None, ge=0, le=100)
    sentiment_api_url: Optional[str] = None


# --- Sentiment upstream ---

class SentimentArticle(BaseModel):
    model_config = ConfigDict(extra="allow")
    title: str
    source: str
    published_at: str
    sentiment: Literal["positive", "neutral", "negative"]
    score: float
    url: Optional[str] = None
    summary: Optional[str] = None
    description: Optional[str] = None


class SentimentMetrics(BaseModel):
    model_config = ConfigDict(extra="allow")
    total_articles: int
    positive_count: int
    negative_count: int
    neutral_count: int
    avg_sentiment: float
    sources_breakdown: Dict[str, int] = Field(default_factory=dict)


class SentimentResponse(BaseModel):
    model_config = ConfigDict(extra="allow")
    ticker: str
    company_name: str
    overall_sentiment: Literal["positive", "neutral", "negative"]
    confidence: float
    metrics: SentimentMetrics
    articles: List[SentimentArticle]
    topics:          Optional[List[TopicKeyword]]  = None
    analyst_ratings: Optional[AnalystRatings]      = None
    correlation:     Optional[PriceCorrelation]    = None


# --- Risk response ---

class MarketMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    vol_ann_30d: Optional[float] = None
    vol_ann_90d: Optional[float] = None
    vol_ann_1y: Optional[float] = None
    downside_deviation_ann: Optional[float] = None
    var_95_hist_1d: Optional[float] = None
    var_99_hist_1d: Optional[float] = None
    var_95_param_1d: Optional[float] = None
    var_99_param_1d: Optional[float] = None
    cvar_95_1d: Optional[float] = None
    max_drawdown: Optional[float] = None
    max_drawdown_duration_days: Optional[int] = None
    beta: Optional[float] = None
    sharpe: Optional[float] = None
    sortino: Optional[float] = None
    skew: Optional[float] = None
    excess_kurtosis: Optional[float] = None
    atr14_pct: Optional[float] = None
    gap_risk_freq: Optional[float] = None
    premarket_gap_pct: Optional[float] = None
    liquidity_score: Optional[float] = None
    range_52w_position: Optional[float] = None


class SentimentRiskMetrics(BaseModel):
    model_config = ConfigDict(extra="forbid")
    negative_ratio: Optional[float] = None
    dispersion: Optional[float] = None
    momentum_24h_vs_7d: Optional[float] = None
    recency_weighted_sentiment: Optional[float] = None
    news_volume_zscore: Optional[float] = None
    source_concentration_hhi: Optional[float] = None
    confidence: Optional[float] = None
    extreme_score_share: Optional[float] = None
    polarity_gap: Optional[float] = None
    sentiment_vol_proxy: Optional[float] = None


class MarketRiskBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    index: float
    metrics: MarketMetrics


class SentimentRiskBlock(BaseModel):
    model_config = ConfigDict(extra="forbid")
    index: float
    metrics: SentimentRiskMetrics


class Recommendations(BaseModel):
    model_config = ConfigDict(extra="forbid")
    suggested_stop_loss_pct: Optional[float] = None
    kelly_fraction_capped: Optional[float] = None
    position_size_pct_of_account: Optional[float] = None
    position_size_usd: Optional[float] = None


class Meta(BaseModel):
    model_config = ConfigDict(extra="forbid")
    sentiment_fetched_at: str
    price_data_as_of: str
    benchmark: Optional[str] = None
    lookback_days: Optional[int] = None
    weights: Optional[Dict[str, float]] = None


class RiskResponse(BaseModel):
    model_config = ConfigDict(extra="forbid")
    ticker: str
    as_of: str
    composite_risk_score: float
    risk_bucket: Literal["low", "moderate", "high"]
    market_risk: MarketRiskBlock
    sentiment_risk: SentimentRiskBlock
    recommendations: Recommendations
    warnings: List[str] = Field(default_factory=list)
    meta: Meta
