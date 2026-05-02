"""HTTP client for the companion sentiment_analysis service.

Validates responses against contracts/sentiment_analysis_to_risk_calculator.response.json.
"""
from __future__ import annotations

import json
import os
import time
from pathlib import Path
from typing import Optional

import httpx
from jsonschema import Draft202012Validator

from ..models.schemas import SentimentResponse


DEFAULT_BASE_URL = os.environ.get("SENTIMENT_API_URL", "http://localhost:8000")
CONTRACTS_DIR = Path(__file__).resolve().parents[3] / "contracts"
_RESPONSE_SCHEMA_PATH = CONTRACTS_DIR / "sentiment_analysis_to_risk_calculator.response.json"


class SentimentServiceDownError(RuntimeError):
    """Raised when the sentiment_analysis service is unreachable."""

    def __init__(self, base_url: str, detail: str):
        self.base_url = base_url
        self.detail = detail
        super().__init__(
            f"sentiment_analysis service is unreachable at {base_url} ({detail}). "
            f"Start it with:  cd sentiment_analysis/backend && python -m app.main"
        )


class SentimentContractError(RuntimeError):
    """Raised when the upstream response violates the JSON Schema contract."""


def _load_validator() -> Draft202012Validator:
    with open(_RESPONSE_SCHEMA_PATH, "r", encoding="utf-8") as f:
        schema = json.load(f)
    return Draft202012Validator(schema)


_validator: Optional[Draft202012Validator] = None


def _get_validator() -> Draft202012Validator:
    global _validator
    if _validator is None:
        _validator = _load_validator()
    return _validator


def check_health(base_url: str = DEFAULT_BASE_URL, timeout: float = 30.0) -> bool:
    url = base_url.rstrip("/") + "/api/health"
    try:
        r = httpx.get(url, timeout=timeout)
        return r.status_code == 200
    except httpx.HTTPError:
        return False


def fetch_sentiment(
    ticker: str,
    company_name: str,
    base_url: str = DEFAULT_BASE_URL,
    timeout: float = 60.0,
    retries: int = 3,
    backoff: float = 1.5,
) -> SentimentResponse:
    """Call POST /api/analyze and return a validated SentimentResponse.

    Raises SentimentServiceDownError if health check fails or all retries timeout.
    Raises SentimentContractError if the response violates the schema.
    """
    base = base_url.rstrip("/")

    if not check_health(base_url=base, timeout=30.0):
        raise SentimentServiceDownError(base, "health check failed")

    url = f"{base}/api/analyze"
    payload = {"ticker": ticker, "company_name": company_name}

    last_err: Optional[str] = None
    for attempt in range(1, retries + 1):
        try:
            r = httpx.post(url, json=payload, timeout=timeout)
            if r.status_code >= 500:
                last_err = f"HTTP {r.status_code}"
            else:
                r.raise_for_status()
                data = r.json()
                errors = sorted(_get_validator().iter_errors(data), key=lambda e: e.path)
                if errors:
                    msgs = "; ".join(f"{list(e.path)}: {e.message}" for e in errors[:3])
                    raise SentimentContractError(
                        f"sentiment_analysis response failed contract validation: {msgs}"
                    )
                return SentimentResponse.model_validate(data)
        except httpx.HTTPError as e:
            last_err = str(e)
        if attempt < retries:
            time.sleep(backoff ** attempt)

    raise SentimentServiceDownError(base, last_err or "unknown error after retries")


def load_sentiment_from_file(path: str) -> SentimentResponse:
    """Dev-only: load a cached sentiment_analysis JSON file (e.g. msft_result.json)."""
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
    errors = sorted(_get_validator().iter_errors(data), key=lambda e: e.path)
    if errors:
        msgs = "; ".join(f"{list(e.path)}: {e.message}" for e in errors[:3])
        raise SentimentContractError(
            f"File {path} failed contract validation: {msgs}"
        )
    return SentimentResponse.model_validate(data)
