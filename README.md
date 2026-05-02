# Risk Calculator

A Python FastAPI service (with CLI) that produces a full risk report for a stock ticker by combining:

- **Historical market data** (via `yfinance`, free; no API key)
- **News sentiment** (via a call to the companion `sentiment_analysis` project's API)

All cross-system payloads are specified as JSON Schemas in `contracts/`. Every metric used is documented in `docs/METRICS.txt` with its definition, formula, and trading-use notes.

## Layout

```
risk_calculator/
├── backend/app/           # FastAPI service + risk engine
├── contracts/             # JSON Schemas (<caller>_to_<callee>.<purpose>.json)
├── docs/METRICS.txt       # Metric dictionary + trading uses
├── examples/              # Sample outputs
├── tests/                 # Contract + smoke tests
├── cli.py                 # CLI client
├── IDEAS_ROADMAP.md       # Future uses of sentiment_analysis output
└── README.md
```

## Install

```powershell
python -m venv venv
venv\Scripts\activate
pip install -r backend\requirements.txt
```

## Prerequisite: start the sentiment_analysis backend

Sentiment is ingested exclusively via the `sentiment_analysis` API. Start it before running the risk calculator:

```powershell
cd ..\sentiment_analysis\backend
python -m app.main
# => http://localhost:8000
```

The risk calculator will call `GET /api/health` and `POST /api/analyze` on that base URL (override with `SENTIMENT_API_URL` env var or `--sentiment-url`).

## Run the CLI

```powershell
python cli.py MSFT --company "Microsoft Corporation" --output report.json
```

## Run the API

```powershell
python -m uvicorn backend.app.main:app --reload --port 8100
# POST http://localhost:8100/api/risk
```

## Contracts

See `contracts/`:

- `client_to_risk_calculator.request.json`
- `risk_calculator_to_client.response.json`
- `risk_calculator_to_sentiment_analysis.request.json`
- `sentiment_analysis_to_risk_calculator.response.json`

## Metrics

See `docs/METRICS.txt` for definitions and trading uses of every metric computed.
