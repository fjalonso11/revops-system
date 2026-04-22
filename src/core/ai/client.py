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

Provide concise, actionable insights. Respond in the same language as the user's question \
(Spanish or English). Focus on trends, anomalies, and recommendations relevant to early-stage \
LatAm B2B startups."""


@lru_cache(maxsize=1)
def get_anthropic() -> anthropic.Anthropic:
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def analyze_metrics(metrics: dict, question: str | None = None) -> str:
    client = get_anthropic()

    user_content = f"Current revenue metrics:\n\n{metrics}"
    if question:
        user_content += f"\n\nSpecific question: {question}"
    else:
        user_content += "\n\nProvide a comprehensive analysis with key insights and top 3 recommendations."

    response = client.messages.create(
        model="claude-sonnet-4-6",
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

    return response.content[0].text
