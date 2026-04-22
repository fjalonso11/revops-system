from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    # API
    api_env: str = "development"
    api_host: str = "0.0.0.0"
    api_port: int = 8000

    # Supabase
    supabase_url: str
    supabase_key: str
    supabase_db_url: str = ""

    # Claude AI
    anthropic_api_key: str

    # HubSpot
    hubspot_access_token: str

    # Slack (optional)
    slack_bot_token: str = ""
    slack_channel_id: str = ""

    # n8n (optional — for inbound webhook signature verification)
    n8n_webhook_secret: str = ""


settings = Settings()
