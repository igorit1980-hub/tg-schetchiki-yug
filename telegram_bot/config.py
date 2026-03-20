from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


BASE_DIR = Path(__file__).resolve().parent.parent


def _load_local_env() -> None:
    env_path = BASE_DIR / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        raw = line.strip()
        if not raw or raw.startswith("#") or "=" not in raw:
            continue
        key, value = raw.split("=", 1)
        key = key.strip()
        value = value.strip().strip("'").strip('"')
        if key and key not in os.environ:
            os.environ[key] = value


@dataclass(frozen=True)
class BotConfig:
    token: str
    manager_username: str
    channel_url: str
    miniapp_url: str
    backend_base_url: str
    bot_name: str


def load_bot_config() -> BotConfig:
    _load_local_env()
    token = os.environ.get("TELEGRAM_BOT_TOKEN", "").strip()
    manager_username = os.environ.get("TELEGRAM_MANAGER_USERNAME", "schetchiki_yug").strip("@ ").strip()
    channel_url = os.environ.get("TELEGRAM_CHANNEL_URL", "https://t.me/schetchiki_yug").strip()
    miniapp_url = os.environ.get(
        "TELEGRAM_MINIAPP_URL",
        "https://igorit1980-hub.github.io/tg-schetchiki-yug/",
    ).strip()
    backend_base_url = os.environ.get(
        "TELEGRAM_BACKEND_BASE_URL",
        "http://127.0.0.1:8787",
    ).rstrip("/")
    bot_name = os.environ.get("TELEGRAM_BOT_NAME", "Счетчики Юг Bot").strip() or "Счетчики Юг Bot"
    return BotConfig(
        token=token,
        manager_username=manager_username,
        channel_url=channel_url,
        miniapp_url=miniapp_url,
        backend_base_url=backend_base_url,
        bot_name=bot_name,
    )
