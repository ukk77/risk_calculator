# Future Uses of `sentiment_analysis` Output — Roadmap

Persistent backlog of features that extend or reuse the JSON output of the
`sentiment_analysis` service. Pick items from here when planning new work on
the risk_calculator or a new sibling project.

## 1. Trading signals

- **Sentiment-momentum long/short**: cross of 24h vs 7d mean score as entry/exit.
- **Event-driven alerts**: fire when `news_volume_zscore > 2` or `extreme_score_share` spikes.
- **Earnings-window tilt**: filter articles to +/- N days around earnings, compute separate sentiment.
- **Divergence scanner**: price up / sentiment down (distribution) or price down / sentiment up (accumulation).

## 2. Portfolio / watchlist

- **Multi-ticker dashboard** ranking holdings by composite risk + recency-weighted sentiment.
- **Sector sentiment heatmap** (aggregate per GICS sector).
- **Sentiment-weighted rebalancer**: overweight positive, underweight negative subject to max risk cap.
- **Correlation matrix** of sentiment shifts across holdings -> diversification check.

## 3. Backtesting

- **Snapshot store**: persist daily sentiment JSONs to parquet; walk-forward-backtest signal vs buy-and-hold.
- **Confidence-bucket hit rate**: forward 1d/5d/20d returns conditional on `confidence` deciles.
- **Source-reliability scoring**: track forward returns by dominant source.

## 4. Alerting / monitoring

- **Telegram / email / Slack** webhook on sentiment flip, negative_ratio threshold breach, or source HHI collapse.
- **Anomaly detection** on article volume (EWMA residual).
- **News-blackout detector** — sudden drop in total_articles.

## 5. Analytics / reporting

- **Topic / entity extraction** from article titles (AI, layoffs, earnings, lawsuits) → thematic sentiment.
- **Persistence study**: autocorrelation and half-life of sentiment per ticker.
- **Source reliability scorecard** updated nightly.

## 6. Risk extensions (feed back into this project)

- **Implied-vol overlay** vs realized vol and sentiment dispersion (pricing gap -> trade).
- **Forward-return correlation** of sentiment shifts per ticker → signal strength weighting.
- **Stress scenarios** built from worst historical negative-news clusters.
- **Allow market-only mode** when sentiment API is down (config flag, graceful degradation).

## 7. UI / integrations

- **CLI `watch`** mode: poll `/api/analyze` every N minutes, re-run risk, diff & alert.
- **Slack / Discord bot**: `/risk TICKER` returns a compact report card.
- **Export to CSV / Parquet** for downstream research.
- **Web dashboard** (Streamlit or React + FastAPI) showing composite, timeline, article feed.

## 8. Data quality

- **De-dup articles** across sources by title+URL similarity.
- **Language filter** (en only or include multilingual with translation step).
- **Timestamp normalization** to exchange local time for intraday use.
