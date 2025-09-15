from pydantic import BaseSettings, Field
from typing import Optional
from pathlib import Path
import os


class Settings(BaseSettings):
    github_token: str = Field(default="", validation_alias="GITHUB_TOKEN")
    github_webhook_secret: str = Field(default="", validation_alias="GITHUB_WEBHOOK_SECRET")

    slack_bot_token: str = Field(default="", validation_alias="SLACK_BOT_TOKEN")
    slack_channel_id: str = Field(default="", validation_alias="SLACK_CHANNEL_ID")

    openai_api_key: str = Field(default="", validation_alias="OPENAI_API_KEY")
    groq_api_key: str = Field(default="", validation_alias="GROQ_API_KEY")
    groq_api_key_file: str = Field(default="", validation_alias="GROQ_API_KEY_FILE")

    summary_model: str = Field(default="gpt-4o-mini", validation_alias="SUMMARY_MODEL")
    groq_model: str = Field(default="llama-3.1-8b-instant", validation_alias="GROQ_MODEL")
    model_checkpoint: str = Field(default="", validation_alias="MODEL_CHECKPOINT")

    cooldown_seconds: int = Field(default=120, validation_alias="COOLDOWN_SECONDS")

    class Config:
        env_file = ".env"
        case_sensitive = False

    def get_groq_api_key(self) -> str:
        if self.groq_api_key:
            return self.groq_api_key
        # Check explicit file env
        candidate = self.groq_api_key_file.strip()
        if candidate:
            path = Path(candidate)
            if path.is_file():
                return path.read_text(encoding="utf-8").strip()
        # Default local file
        default_path = Path(".groq_api_key")
        if default_path.is_file():
            return default_path.read_text(encoding="utf-8").strip()
        # Also allow process env directly if set outside pydantic
        env_val = os.getenv("GROQ_API_KEY", "").strip()
        return env_val


settings = Settings()  # type: ignore[misc]
