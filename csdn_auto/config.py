from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


def load_dotenv(path: str | Path = ".env") -> None:
    """加载简单的 KEY=VALUE 配置，不覆盖已存在的环境变量。"""
    env_path = Path(path)
    if not env_path.exists():
        return

    for raw_line in env_path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip()
        if value[:1] in {'"', "'"} and value[-1:] == value[:1]:
            value = value[1:-1]
        os.environ.setdefault(key, value)


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise ValueError(f"缺少配置 {name}，请检查 .env")
    return value


@dataclass(frozen=True)
class Settings:
    ai_base_url: str
    ai_api_key: str
    ai_model: str
    ai_connect_timeout: int
    ai_timeout: int
    csdn_cookie: str
    csdn_x_ca_key: str
    csdn_x_ca_secret: str
    csdn_x_ca_nonce: str
    csdn_x_ca_signature: str
    csdn_article_id: str
    csdn_tags: str
    csdn_category: str
    prompt_history_path: str
    prompt_scene_count: int
    prompt_tech_min: int
    prompt_tech_max: int
    prompt_recent_window: int
    schedule_interval_hours: float
    schedule_timezone: str

    @classmethod
    def from_env(cls, require_ai: bool = True) -> "Settings":
        load_dotenv()
        api_key = os.getenv("AI_API_KEY", "").strip()
        if require_ai and not api_key:
            raise ValueError("缺少配置 AI_API_KEY，请检查 .env")

        return cls(
            ai_base_url=os.getenv("AI_BASE_URL", "https://api.openai.com/v1").rstrip("/"),
            ai_api_key=api_key,
            ai_model=os.getenv("AI_MODEL", "gpt-5-mini").strip(),
            ai_connect_timeout=int(os.getenv("AI_CONNECT_TIMEOUT", "10")),
            ai_timeout=int(os.getenv("AI_TIMEOUT", "120")),
            csdn_cookie=_required("CSDN_COOKIE"),
            csdn_x_ca_key=os.getenv("CSDN_X_CA_KEY", "203803574").strip(),
            csdn_x_ca_secret=os.getenv("CSDN_X_CA_SECRET", "").strip(),
            csdn_x_ca_nonce=os.getenv("CSDN_X_CA_NONCE", "").strip(),
            csdn_x_ca_signature=os.getenv("CSDN_X_CA_SIGNATURE", "").strip(),
            csdn_article_id=os.getenv("CSDN_ARTICLE_ID", "").strip(),
            csdn_tags=os.getenv("CSDN_TAGS", "java").strip(),
            csdn_category=os.getenv("CSDN_CATEGORY", "").strip(),
            prompt_history_path=os.getenv(
                "PROMPT_HISTORY_PATH", ".state/prompt_history.json"
            ).strip(),
            prompt_scene_count=int(os.getenv("PROMPT_SCENE_COUNT", "1")),
            prompt_tech_min=int(os.getenv("PROMPT_TECH_MIN", "2")),
            prompt_tech_max=int(os.getenv("PROMPT_TECH_MAX", "3")),
            prompt_recent_window=int(os.getenv("PROMPT_RECENT_WINDOW", "30")),
            schedule_interval_hours=float(
                os.getenv("SCHEDULE_INTERVAL_HOURS", "12")
            ),
            schedule_timezone=os.getenv("SCHEDULE_TIMEZONE", "Asia/Shanghai").strip(),
        )
