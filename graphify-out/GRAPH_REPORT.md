# Graph Report - risk_calculator  (2026-05-06)

## Corpus Check
- 19 files · ~8,185 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 154 nodes · 232 edges · 16 communities
- Extraction: 92% EXTRACTED · 8% INFERRED · 0% AMBIGUOUS · INFERRED: 19 edges (avg confidence: 0.77)
- Token cost: 0 input · 0 output

## Community Hubs (Navigation)
- [[_COMMUNITY_Community 0|Community 0]]
- [[_COMMUNITY_Community 1|Community 1]]
- [[_COMMUNITY_Community 2|Community 2]]
- [[_COMMUNITY_Community 3|Community 3]]
- [[_COMMUNITY_Community 4|Community 4]]
- [[_COMMUNITY_Community 5|Community 5]]
- [[_COMMUNITY_Community 6|Community 6]]
- [[_COMMUNITY_Community 7|Community 7]]
- [[_COMMUNITY_Community 8|Community 8]]
- [[_COMMUNITY_Community 9|Community 9]]
- [[_COMMUNITY_Community 10|Community 10]]
- [[_COMMUNITY_Community 11|Community 11]]

## God Nodes (most connected - your core abstractions)
1. `compute_market_metrics()` - 19 edges
2. `build_report()` - 12 edges
3. `compute_sentiment_metrics()` - 10 edges
4. `Future Uses of `sentiment_analysis` Output — Roadmap` - 9 edges
5. `Risk Calculator` - 8 edges
6. `main()` - 7 edges
7. `SentimentServiceDownError` - 6 edges
8. `SentimentContractError` - 6 edges
9. `fetch_sentiment()` - 6 edges
10. `init_db()` - 5 edges

## Surprising Connections (you probably didn't know these)
- `main()` --calls--> `RiskRequest`  [INFERRED]
  cli.py → backend/app/models/schemas.py
- `main()` --calls--> `Weights`  [INFERRED]
  cli.py → backend/app/models/schemas.py
- `main()` --calls--> `build_report()`  [INFERRED]
  cli.py → backend/app/services/report.py
- `test_risk_request_defaults()` --calls--> `RiskRequest`  [INFERRED]
  tests/test_contracts.py → backend/app/models/schemas.py
- `compute_market_metrics()` --calls--> `log_returns()`  [INFERRED]
  backend/app/services/risk_metrics.py → backend/app/utils/stats.py

## Communities (16 total, 0 thin omitted)

### Community 0 - "Community 0"
Cohesion: 0.18
Nodes (19): atr14_pct(), beta(), compute_market_metrics(), conditional_var(), downside_deviation_annual(), excess_kurtosis(), gap_risk_frequency(), historical_var() (+11 more)

### Community 1 - "Community 1"
Cohesion: 0.19
Nodes (18): BaseModel, AnalystRatings, LeadLagPoint, MarketMetrics, MarketRiskBlock, Meta, PriceCorrelation, Pydantic models matching the JSON Schemas in contracts/. (+10 more)

### Community 2 - "Community 2"
Cohesion: 0.19
Nodes (11): _avg(), compute_indices(), _market_contributions(), Normalize sub-metrics to 0-100 risk contributions and combine into a composite s, _sentiment_contributions(), annualize_vol(), clip01(), log_returns() (+3 more)

### Community 3 - "Community 3"
Cohesion: 0.21
Nodes (13): RuntimeError, check_health(), fetch_sentiment(), _get_validator(), load_sentiment_from_file(), _load_validator(), HTTP client for the companion sentiment_analysis service.  Validates responses a, Dev-only: load a cached sentiment_analysis JSON file (e.g. msft_result.json). (+5 more)

### Community 4 - "Community 4"
Cohesion: 0.2
Nodes (10): get_risk_history(), FastAPI entry point for risk_calculator., Return historical risk snapshots for a ticker (newest first).      Each snapshot, risk(), build_report(), _build_warnings(), _kelly_fraction_capped(), _position_size() (+2 more)

### Community 5 - "Community 5"
Cohesion: 0.14
Nodes (13): code:block1 (risk_calculator/), code:powershell (python -m venv venv), code:powershell (cd ..\sentiment_analysis\backend), code:powershell (python cli.py MSFT --company "Microsoft Corporation" --outpu), code:powershell (python -m uvicorn backend.app.main:app --reload --port 8100), Contracts, Install, Layout (+5 more)

### Community 6 - "Community 6"
Cohesion: 0.29
Nodes (12): compute_sentiment_metrics(), dispersion(), extreme_score_share(), momentum_24h_vs_7d(), negative_ratio(), news_volume_zscore(), _parse_ts(), polarity_gap() (+4 more)

### Community 7 - "Community 7"
Cohesion: 0.2
Nodes (9): 1. Trading signals, 2. Portfolio / watchlist, 3. Backtesting, 4. Alerting / monitoring, 5. Analytics / reporting, 6. Risk extensions (feed back into this project), 7. UI / integrations, 8. Data quality (+1 more)

### Community 8 - "Community 8"
Cohesion: 0.36
Nodes (8): _get_conn(), get_history(), init_db(), SQLite-based historical risk tracking.  Mirrors sentiment_analysis/backend/app/s, Persist one RiskResponse (as a dict) to the DB.      Expects the dict form of th, Return the last *limit* snapshots for *ticker*, newest first., Create the risk_snapshots table and index if they don't exist., save_snapshot()

### Community 9 - "Community 9"
Cohesion: 0.32
Nodes (7): _cache_path(), fetch_ohlcv(), fetch_risk_free_rate_annual(), _fresh(), Historical price data fetch (yfinance) with simple on-disk cache., Return daily OHLCV indexed by date (UTC-naive). Uses parquet cache., Return annualized risk-free rate proxy (^IRX is quoted as % annualized).

### Community 10 - "Community 10"
Cohesion: 0.33
Nodes (4): _load_schema(), Validate contract schemas and Pydantic models against the sample msft_result.jso, test_risk_request_defaults(), test_sample_matches_sentiment_response_schema()

### Community 11 - "Community 11"
Cohesion: 0.53
Nodes (5): main(), _parse_args(), _print_report(), Risk Calculator CLI.  Examples:   python cli.py MSFT --company "Microsoft Corpor, _serve()

## Knowledge Gaps
- **41 isolated node(s):** `Risk Calculator CLI.  Examples:   python cli.py MSFT --company "Microsoft Corpor`, `FastAPI entry point for risk_calculator.`, `Return historical risk snapshots for a ticker (newest first).      Each snapshot`, `Pydantic models matching the JSON Schemas in contracts/.`, `Normalize sub-metrics to 0-100 risk contributions and combine into a composite s` (+36 more)
  These have ≤1 connection - possible missing edges or undocumented components.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `RiskRequest` connect `Community 1` to `Community 10`, `Community 11`?**
  _High betweenness centrality (0.088) - this node is a cross-community bridge._
- **Why does `fetch_ohlcv()` connect `Community 9` to `Community 3`?**
  _High betweenness centrality (0.066) - this node is a cross-community bridge._
- **Why does `SentimentResponse` connect `Community 1` to `Community 3`?**
  _High betweenness centrality (0.063) - this node is a cross-community bridge._
- **Are the 3 inferred relationships involving `compute_market_metrics()` (e.g. with `log_returns()` and `MarketMetrics`) actually correct?**
  _`compute_market_metrics()` has 3 INFERRED edges - model-reasoned connections that need verification._
- **Are the 7 inferred relationships involving `build_report()` (e.g. with `main()` and `risk()`) actually correct?**
  _`build_report()` has 7 INFERRED edges - model-reasoned connections that need verification._
- **What connects `Risk Calculator CLI.  Examples:   python cli.py MSFT --company "Microsoft Corpor`, `FastAPI entry point for risk_calculator.`, `Return historical risk snapshots for a ticker (newest first).      Each snapshot` to the rest of the system?**
  _41 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `Community 5` be split into smaller, more focused modules?**
  _Cohesion score 0.14 - nodes in this community are weakly interconnected._