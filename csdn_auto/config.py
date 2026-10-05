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


def _boolean(name: str, default: bool) -> bool:
    raw_value = os.getenv(name)
    if raw_value is None:
        return default
    value = raw_value.strip().lower()
    if value in {"1", "true", "yes", "on"}:
        return True
    if value in {"0", "false", "no", "off"}:
        return False
    raise ValueError(f"配置 {name} 必须是 true/false")


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
    rag_enabled: bool = True
    rag_knowledge_dir: str = "knowledge"
    rag_top_k: int = 4
    rag_chunk_size: int = 1200
    rag_chunk_overlap: int = 150
    rag_backend: str = "chroma"
    rag_vector_path: str = ".state/chroma"
    rag_collection: str = "csdn_mcp_knowledge"
    rag_embedding_batch_size: int = 32
    embedding_base_url: str = "https://api.openai.com/v1"
    embedding_api_key: str = ""
    embedding_model: str = "text-embedding-3-small"
    embedding_timeout: int = 60
    rag_min_score: float = 0.2
    embedding_dimensions: int | None = None
    embedding_failover_enabled: bool = False
    embedding_query_instruction: str = ""
    embedding_document_instruction: str = ""
    ai_disable_thinking: bool = False

    @classmethod
    def from_env(cls, require_ai: bool = True) -> "Settings":
        load_dotenv()
        api_key = os.getenv("AI_API_KEY", "").strip()
        if require_ai and not api_key:
            raise ValueError("缺少配置 AI_API_KEY，请检查 .env")
        ai_base_url = os.getenv(
            "AI_BASE_URL", "https://api.openai.com/v1"
        ).rstrip("/")
        configured_embedding_url = os.getenv("EMBEDDING_BASE_URL", "").strip()
        embedding_base_url = (configured_embedding_url or ai_base_url).rstrip("/")
        configured_embedding_key = os.getenv("EMBEDDING_API_KEY", "").strip()
        embedding_api_key = (
            configured_embedding_key
            if configured_embedding_url
            else configured_embedding_key or api_key
        )
        dimensions = os.getenv("EMBEDDING_DIMENSIONS", "").strip()

        return cls(
            ai_base_url=ai_base_url,
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
            csdn_tags=os.getenv("CSDN_TAGS", "MCP").strip(),
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
            rag_enabled=_boolean("RAG_ENABLED", True),
            rag_knowledge_dir=os.getenv("RAG_KNOWLEDGE_DIR", "knowledge").strip(),
            rag_top_k=int(os.getenv("RAG_TOP_K", "4")),
            rag_chunk_size=int(os.getenv("RAG_CHUNK_SIZE", "1200")),
            rag_chunk_overlap=int(os.getenv("RAG_CHUNK_OVERLAP", "150")),
            rag_backend=os.getenv("RAG_BACKEND", "chroma").strip().lower(),
            rag_vector_path=os.getenv("RAG_VECTOR_PATH", ".state/chroma").strip(),
            rag_collection=os.getenv(
                "RAG_COLLECTION", "csdn_mcp_knowledge"
            ).strip(),
            rag_embedding_batch_size=int(
                os.getenv("RAG_EMBEDDING_BATCH_SIZE", "32")
            ),
            embedding_base_url=embedding_base_url,
            embedding_api_key=embedding_api_key,
            embedding_model=os.getenv(
                "EMBEDDING_MODEL", "text-embedding-3-small"
            ).strip(),
            embedding_timeout=int(os.getenv("EMBEDDING_TIMEOUT", "60")),
            rag_min_score=float(os.getenv("RAG_MIN_SCORE", "0.2")),
            embedding_dimensions=int(dimensions) if dimensions else None,
            embedding_failover_enabled=_boolean(
                "EMBEDDING_FAILOVER_ENABLED", False
            ),
            embedding_query_instruction=os.getenv(
                "EMBEDDING_QUERY_INSTRUCTION", ""
            ).strip(),
            embedding_document_instruction=os.getenv(
                "EMBEDDING_DOCUMENT_INSTRUCTION", ""
            ).strip(),
            ai_disable_thinking=_boolean("AI_DISABLE_THINKING", False),
        )
