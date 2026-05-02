"""Risk Calculator CLI.

Examples:
  python cli.py MSFT --company "Microsoft Corporation"
  python cli.py NVDA --company "NVIDIA Corp" --output nvda.json
  python cli.py --serve
  python cli.py MSFT --dev-sentiment-file ../sentiment_analysis/msft_result.json
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from rich.console import Console
from rich.table import Table

from backend.app.models.schemas import RiskRequest, Weights
from backend.app.services import (
    market_data,
    risk_metrics,
    sentiment_client,
    sentiment_risk,
)
from backend.app.services.report import build_report

console = Console()


def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Risk Calculator CLI")
    p.add_argument("ticker", nargs="?", help="Stock ticker (uppercase)")
    p.add_argument("--company", help="Company name (defaults to ticker)")
    p.add_argument("--sentiment-url", default=None, help="Base URL for sentiment_analysis API")
    p.add_argument("--lookback", type=int, default=504, help="Lookback days (default 504)")
    p.add_argument("--benchmark", default="SPY")
    p.add_argument("--w-market", type=float, default=0.7)
    p.add_argument("--w-sentiment", type=float, default=0.3)
    p.add_argument("--account", type=float, default=None, help="Account size in USD")
    p.add_argument("--max-risk-pct", type=float, default=None, help="Max %% of account to risk")
    p.add_argument("--output", help="Write full JSON report to this path")
    p.add_argument("--serve", action="store_true", help="Launch FastAPI server instead of running a report")
    p.add_argument("--port", type=int, default=8100)
    p.add_argument(
        "--dev-sentiment-file",
        help="DEV ONLY: load sentiment from a local JSON file instead of calling the API.",
    )
    return p.parse_args()


def _print_report(rep) -> None:
    d = rep.model_dump()
    console.rule(f"[bold]Risk Report: {d['ticker']}  ({d['as_of']})[/bold]")

    score = d["composite_risk_score"]
    bucket = d["risk_bucket"]
    color = {"low": "green", "moderate": "yellow", "high": "red"}[bucket]
    console.print(
        f"Composite Risk: [bold {color}]{score:.1f}/100  ({bucket.upper()})[/bold {color}]"
    )
    console.print(
        f"  Market index: {d['market_risk']['index']:.1f}   "
        f"Sentiment index: {d['sentiment_risk']['index']:.1f}\n"
    )

    def _fmt(v):
        if v is None:
            return "-"
        if isinstance(v, float):
            return f"{v:.4f}"
        return str(v)

    for block_name in ("market_risk", "sentiment_risk"):
        t = Table(title=block_name.replace("_", " ").title(), show_edge=False)
        t.add_column("Metric", style="cyan")
        t.add_column("Value", justify="right")
        for k, v in d[block_name]["metrics"].items():
            t.add_row(k, _fmt(v))
        console.print(t)

    t = Table(title="Recommendations", show_edge=False)
    t.add_column("Metric", style="cyan")
    t.add_column("Value", justify="right")
    for k, v in d["recommendations"].items():
        t.add_row(k, _fmt(v))
    console.print(t)

    if d["warnings"]:
        console.print("\n[bold yellow]Warnings:[/bold yellow]")
        for w in d["warnings"]:
            console.print(f"  - {w}")


def _serve(port: int) -> None:
    import uvicorn
    uvicorn.run("backend.app.main:app", host="0.0.0.0", port=port, reload=False)


def main() -> int:
    args = _parse_args()

    if args.serve:
        _serve(args.port)
        return 0

    if not args.ticker:
        console.print("[red]Error:[/red] ticker is required (or use --serve).")
        return 2

    ticker = args.ticker.upper()
    company = args.company or ticker

    req = RiskRequest(
        ticker=ticker,
        company_name=company,
        lookback_days=args.lookback,
        benchmark=args.benchmark,
        weights=Weights(market=args.w_market, sentiment=args.w_sentiment),
        account_size=args.account,
        max_risk_pct=args.max_risk_pct,
        sentiment_api_url=args.sentiment_url,
    )

    # 1. Sentiment.
    base_url = req.sentiment_api_url or sentiment_client.DEFAULT_BASE_URL
    if args.dev_sentiment_file:
        console.print(f"[yellow]DEV mode:[/yellow] loading sentiment from {args.dev_sentiment_file}")
        try:
            s_resp = sentiment_client.load_sentiment_from_file(args.dev_sentiment_file)
        except sentiment_client.SentimentContractError as e:
            console.print(f"[red]Contract error:[/red] {e}")
            return 4
    else:
        console.print(f"[dim]Checking sentiment_analysis at {base_url} ...[/dim]")
        if not sentiment_client.check_health(base_url=base_url):
            console.print(
                f"[red]sentiment_analysis service is DOWN at {base_url}.[/red]\n"
                "Start it with:\n"
                "  cd sentiment_analysis/backend && python -m app.main"
            )
            return 3
        try:
            s_resp = sentiment_client.fetch_sentiment(
                ticker=ticker, company_name=company, base_url=base_url
            )
        except sentiment_client.SentimentServiceDownError as e:
            console.print(f"[red]{e}[/red]")
            return 3
        except sentiment_client.SentimentContractError as e:
            console.print(f"[red]Contract error:[/red] {e}")
            return 4

    sentiment_fetched_at = datetime.now(timezone.utc).isoformat()

    # 2. Market data.
    console.print(f"[dim]Fetching {req.lookback_days}d of price data for {ticker} and {req.benchmark} ...[/dim]")
    ohlc = market_data.fetch_ohlcv(ticker, req.lookback_days)
    bench = market_data.fetch_ohlcv(req.benchmark, req.lookback_days)
    rf = market_data.fetch_risk_free_rate_annual()
    price_as_of = ohlc.index[-1].date().isoformat()

    # 3. Metrics + 4. Report.
    m_metrics = risk_metrics.compute_market_metrics(ohlc, bench, rf_annual=rf)
    s_metrics = sentiment_risk.compute_sentiment_metrics(s_resp)
    report = build_report(
        req=req,
        market=m_metrics,
        sentiment=s_metrics,
        s_resp=s_resp,
        price_data_as_of=price_as_of,
        sentiment_fetched_at=sentiment_fetched_at,
    )

    _print_report(report)

    if args.output:
        from pathlib import Path
        out_path = Path(args.output)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(report.model_dump(), f, indent=2)
        console.print(f"\n[green]Full report written to[/green] {out_path}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
