"""Validate contract schemas and Pydantic models against the sample msft_result.json."""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from backend.app.models.schemas import (
    RiskRequest,
    SentimentResponse,
)

ROOT = Path(__file__).resolve().parents[1]
CONTRACTS = ROOT / "contracts"
SAMPLE = ROOT.parent / "sentiment_analysis" / "api_test_result.json"


def _load_schema(name: str) -> dict:
    with open(CONTRACTS / name, "r", encoding="utf-8") as f:
        return json.load(f)


def test_all_contracts_parse_as_json_schema():
    for path in CONTRACTS.glob("*.json"):
        with open(path, "r", encoding="utf-8") as f:
            schema = json.load(f)
        # Will raise if schema itself is invalid.
        Draft202012Validator.check_schema(schema)


@pytest.mark.skipif(not SAMPLE.exists(), reason="api_test_result.json not present")
def test_sample_matches_sentiment_response_schema():
    schema = _load_schema("sentiment_analysis_to_risk_calculator.response.json")
    with open(SAMPLE, "r", encoding="utf-8") as f:
        data = json.load(f)
    errors = sorted(Draft202012Validator(schema).iter_errors(data), key=lambda e: e.path)
    assert not errors, f"Schema violations: {[(list(e.path), e.message) for e in errors[:5]]}"


@pytest.mark.skipif(not SAMPLE.exists(), reason="api_test_result.json not present")
def test_sample_parses_as_pydantic_model():
    with open(SAMPLE, "r", encoding="utf-8") as f:
        data = json.load(f)
    resp = SentimentResponse.model_validate(data)
    assert resp.ticker == data["ticker"]
    assert resp.metrics.total_articles == len(resp.articles) or len(resp.articles) <= resp.metrics.total_articles


def test_risk_request_defaults():
    req = RiskRequest(ticker="MSFT")
    assert req.lookback_days == 504
    assert req.benchmark == "SPY"
    assert req.weights.market == 0.7 and req.weights.sentiment == 0.3
