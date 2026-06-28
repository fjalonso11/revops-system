"""
Exa API client for the RevOps platform.
Shared by Build A (Account Enrichment) and Build B (Churn Signal Detection).

Usage:
    from src.integrations.exa.client import get_exa, company_brief
"""

import os
import time
import logging
from functools import lru_cache
from exa_py import Exa
from src.core.config import settings

log = logging.getLogger(__name__)

# Output schema for company enrichment — shared by Build A and B
# Max nesting depth 2, max 10 properties (Exa constraint)
COMPANY_BRIEF_SCHEMA = {
    "type": "object",
    "required": ["company_name", "summary", "recent_signals", "source_urls"],
    "properties": {
        "company_name": {
            "type": "string",
            "description": "Name of the company"
        },
        "summary": {
            "type": "string",
            "description": "2-3 sentence summary of the most important recent developments"
        },
        "recent_signals": {
            "type": "string",
            "description": "Key signals: funding, product launches, leadership changes, expansion, or contraction in the last 90 days"
        },
        "risk_indicators": {
            "type": "string",
            "description": "Any negative signals: bad press, executive departures, layoffs, competitor wins, financial distress"
        },
        "source_urls": {
            "type": "string",
            "description": "Comma-separated URLs of the most relevant sources"
        }
    }
}

# Negative-signal variant for Build B (churn detection)
CHURN_SIGNAL_SCHEMA = {
    "type": "object",
    "required": ["company_name", "churn_risk_summary", "negative_signals", "source_urls"],
    "properties": {
        "company_name": {
            "type": "string",
            "description": "Name of the company"
        },
        "churn_risk_summary": {
            "type": "string",
            "description": "2-3 sentence assessment of external churn risk signals"
        },
        "negative_signals": {
            "type": "string",
            "description": "Specific negative signals: bad press, leadership departures, layoffs, budget cuts, competitor wins, financial distress"
        },
        "severity": {
            "type": "string",
            "description": "Risk severity: low, medium, high, or critical based on signals found"
        },
        "source_urls": {
            "type": "string",
            "description": "Comma-separated URLs of the most relevant sources"
        }
    }
}


@lru_cache(maxsize=1)
def get_exa() -> Exa:
    """Returns a cached Exa client instance."""
    api_key = settings.exa_api_key
    if not api_key:
        raise ValueError("EXA_API_KEY is not set in environment variables")
    return Exa(api_key=api_key)


def company_brief(
    domain: str,
    company_name: str,
    days: int = 90,
    churn_mode: bool = False,
    max_retries: int = 3,
) -> dict | None:
    """
    Fetches a structured company brief from Exa using /search + outputSchema.

    Args:
        domain: Company domain (e.g., "clip.mx")
        company_name: Human-readable company name for the query
        days: How many days of news to search (default 90)
        churn_mode: If True, uses the churn signal schema focused on negative signals
        max_retries: Number of retries on rate limit (429)

    Returns:
        Structured dict matching the output schema, or None if search fails
    """
    schema = CHURN_SIGNAL_SCHEMA if churn_mode else COMPANY_BRIEF_SCHEMA

    if churn_mode:
        query = (
            f"{company_name} ({domain}) negative news layoffs executive departure "
            f"financial distress competitor wins budget cuts"
        )
        system_prompt = (
            "Focus exclusively on negative signals. Ignore positive news. "
            "Prefer credible sources: business press, LinkedIn announcements, "
            "regulatory filings. Include source URLs for every finding."
        )
    else:
        query = (
            f"{company_name} ({domain}) recent news funding product launch "
            f"expansion leadership hiring"
        )
        system_prompt = (
            "Prefer official company pages, credible business press, and funding databases. "
            "Collapse duplicate reporting. Include source URLs for every key finding."
        )

    exa = get_exa()

    for attempt in range(max_retries):
        try:
            results = exa.search(
                query,
                type="auto",
                num_results=5,
                # Domain filter removed — neural search finds relevant coverage
                # across the web better than restricting to the company's own domain
                start_published_date=_days_ago_iso(days),
                system_prompt=system_prompt,
                output_schema=schema,
                contents={"highlights": True},
            )

            if results.output and results.output.content:
                log.info(
                    "Exa brief fetched for %s (churn_mode=%s)", company_name, churn_mode
                )
                return results.output.content

            log.warning("Exa returned no output content for %s", company_name)
            return None

        except Exception as e:
            if "429" in str(e) and attempt < max_retries - 1:
                wait = 2 ** attempt  # exponential backoff: 1s, 2s, 4s
                log.warning(
                    "Exa rate limit hit for %s — retrying in %ds (attempt %d/%d)",
                    company_name, wait, attempt + 1, max_retries
                )
                time.sleep(wait)
            else:
                log.error("Exa search failed for %s: %s", company_name, e)
                return None

    return None


def _days_ago_iso(days: int) -> str:
    """Returns an ISO date string for N days ago."""
    from datetime import datetime, timedelta, timezone
    dt = datetime.now(timezone.utc) - timedelta(days=days)
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")
