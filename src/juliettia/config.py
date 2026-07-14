from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

DEFAULT_MODEL = "mistral-large-latest"
DEFAULT_CLIENT_SECRET_PATH = "credentials/client_secret.json"
DEFAULT_TOKEN_PATH = "credentials/token.json"
DEFAULT_PROMPT_PATH = "prompts/reply_instructions.txt"
DEFAULT_LABEL_NAME = "AI-Processed"
DEFAULT_LOG_LEVEL = "INFO"


class ConfigError(RuntimeError):
    """Raised when required configuration is missing or invalid."""


def _env_bool(name: str, default: bool) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in {"1", "true", "yes", "on"}


@dataclass(frozen=True)
class Config:
    mistral_api_key: str
    mistral_model: str
    target_recipient_email: str
    gmail_client_secret_path: Path
    gmail_token_path: Path
    reply_prompt_path: Path
    processed_label_name: str
    log_level: str
    dry_run: bool

    @property
    def reply_instructions(self) -> str:
        if not self.reply_prompt_path.is_file():
            raise ConfigError(
                f"Reply prompt file not found: {self.reply_prompt_path}"
            )
        return self.reply_prompt_path.read_text(encoding="utf-8").strip()


def load_config(*, strict: bool = True) -> Config:
    """Load configuration from the environment.

    When ``strict`` is False, required-variable validation is skipped. This is
    used by the ``--auth-only`` flow, which only needs the Gmail credential
    paths and doesn't require a Mistral API key or target recipient yet.
    """
    load_dotenv()

    mistral_api_key = os.environ.get("MISTRAL_API_KEY", "").strip()
    target_recipient_email = os.environ.get("TARGET_RECIPIENT_EMAIL", "").strip()

    if strict:
        missing = [
            name
            for name, value in (
                ("MISTRAL_API_KEY", mistral_api_key),
                ("TARGET_RECIPIENT_EMAIL", target_recipient_email),
            )
            if not value
        ]
        if missing:
            raise ConfigError(
                "Missing required environment variable(s): " + ", ".join(missing)
            )

    return Config(
        mistral_api_key=mistral_api_key,
        mistral_model=os.environ.get("MISTRAL_MODEL", DEFAULT_MODEL).strip(),
        target_recipient_email=target_recipient_email,
        gmail_client_secret_path=Path(
            os.environ.get("GMAIL_CLIENT_SECRET_PATH", DEFAULT_CLIENT_SECRET_PATH)
        ),
        gmail_token_path=Path(
            os.environ.get("GMAIL_TOKEN_PATH", DEFAULT_TOKEN_PATH)
        ),
        reply_prompt_path=Path(
            os.environ.get("REPLY_PROMPT_PATH", DEFAULT_PROMPT_PATH)
        ),
        processed_label_name=os.environ.get(
            "PROCESSED_LABEL_NAME", DEFAULT_LABEL_NAME
        ).strip(),
        log_level=os.environ.get("LOG_LEVEL", DEFAULT_LOG_LEVEL).strip().upper(),
        dry_run=_env_bool("DRY_RUN", False),
    )
