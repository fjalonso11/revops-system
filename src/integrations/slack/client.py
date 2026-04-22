from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError
from src.core.config import settings


def _client() -> WebClient:
    return WebClient(token=settings.slack_bot_token)


def send_message(text: str, channel: str | None = None) -> bool:
    if not settings.slack_bot_token:
        return False
    try:
        _client().chat_postMessage(
            channel=channel or settings.slack_channel_id,
            text=text,
        )
        return True
    except SlackApiError:
        return False


def send_sync_notification(source: str, result: dict) -> None:
    counts = {k: v for k, v in result.items() if k != "errors" and isinstance(v, int)}
    errors = result.get("errors", [])
    status = "✅" if not errors else "⚠️"
    lines = [f"{status} *{source} sync complete*"] + [
        f"  • {k}: {v}" for k, v in counts.items()
    ]
    if errors:
        lines.append(f"  Errors: {', '.join(str(e) for e in errors)}")
    send_message("\n".join(lines))


def send_metrics_alert(layer: str, metric: str, value: float, threshold: float) -> None:
    send_message(
        f"🚨 *RevOps Alert* — {layer}/{metric} is {value:.2f} (threshold: {threshold:.2f})"
    )
