import json
import anthropic
from functools import lru_cache
from src.core.config import settings

# Cached at the ephemeral tier — survives for 5 min per cache TTL.
# Saves ~800 input tokens on every /ai/analyze call.
_SYSTEM_PROMPT = """You are a RevOps analyst AI for LatAm startups. You analyze revenue metrics \
across three layers:

- Volume: new business growth (new customers, new MRR, TPV)
- Velocity: sales efficiency (lead-to-cash cycle times, conversion rates by funnel stage)
- Yield: revenue quality (NRR, expansion MRR, churn MRR)

When prior period metrics are provided, always reason about direction first — whether each metric \
is improving, deteriorating, or flat — before commenting on absolute values. A metric moving in \
the wrong direction is more urgent than a metric that is simply low. When prior metrics are not \
available, analyze the current snapshot and note that trend context is not yet available.

Provide concise, actionable insights. Respond in the same language as the user's question \
(Spanish or English). Focus on trends, anomalies, and recommendations relevant to early-stage \
LatAm B2B startups."""

_FLAGS_PROMPT = """You are a structured data extractor. Given a RevOps analysis text, extract \
risk flags and return ONLY valid JSON with no explanation, no markdown, no backticks.

Return exactly this structure:
{
  "yield_status": "critical" | "deteriorating" | "flat" | "healthy",
  "churn_risk": true | false,
  "at_risk_domains": []
}

Rules:
- yield_status is "critical" if NRR is negative or churn exceeds expansion significantly
- yield_status is "deteriorating" if NRR is declining or below 100%
- churn_risk is true if yield_status is "critical" or "deteriorating"
- at_risk_domains should be empty [] unless specific company domains are mentioned in the analysis"""


@lru_cache(maxsize=1)
def get_anthropic() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def _extract_risk_flags(analysis_text: str) -> dict:
    """
    Makes a lightweight second Claude call to extract structured risk flags
    from the narrative analysis. Returns a safe default if extraction fails.
    """
    client = get_anthropic()

    try:
        response = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=256,
            messages=[{
                "role": "user",
                "content": f"{_FLAGS_PROMPT}\n\nAnalysis to extract from:\n\n{analysis_text}"
            }],
        )
        raw = response.content[0].text.strip()
        # Strip markdown code fences if Claude wraps the JSON
        raw = raw.replace("```json", "").replace("```", "").strip()
        return json.loads(raw)
    except Exception:
        # Safe default — don't crash the main pipeline if extraction fails
        return {
            "yield_status": "unknown",
            "churn_risk": False,
            "at_risk_domains": []
        }


def analyze_metrics(
    metrics: dict,
    question: str | None = None,
    prior_metrics: dict | None = None,
) -> dict:
    """
    Returns a dict with two keys:
    - analysis: the narrative text analysis
    - risk_flags: structured flags for n8n routing (yield_status, churn_risk, at_risk_domains)
    """
    client = get_anthropic()

    user_content = f"Current revenue metrics:\n\n{metrics}"

    if prior_metrics:
        user_content += f"\n\nPrior period metrics (for trend comparison):\n\n{prior_metrics}"
        user_content += "\n\nAnalyze direction first — what is improving, deteriorating, or flat — then provide absolute context and top 3 recommendations."
    elif question:
        user_content += f"\n\nSpecific question: {question}"
    else:
        user_content += "\n\nPrior period data is not yet available. Provide a comprehensive analysis of current state with key insights and top 3 recommendations."

    response = client.messages.create(
        model="claude-haiku-4-5-20251001",
        max_tokens=2048,
        system=[
            {
                "type": "text",
                "text": _SYSTEM_PROMPT,
                "cache_control": {"type": "ephemeral"},
            }
        ],
        messages=[{"role": "user", "content": user_content}],
    )

    analysis_text = response.content[0].text
    risk_flags = _extract_risk_flags(analysis_text)

    return {
        "analysis": analysis_text,
        "risk_flags": risk_flags,
    }
