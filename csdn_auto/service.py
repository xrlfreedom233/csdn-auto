from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from .ai import AIClient, GeneratedArticle
from .config import Settings
from .csdn import CSDNClient, PublishResult


class PublishingService:
    def __init__(self, settings: Settings):
        self.ai = AIClient(settings)
        self.csdn = CSDNClient(settings)

    def generate(self) -> GeneratedArticle:
        return self.ai.generate()

    def run_once(self, dry_run: bool = False) -> tuple[GeneratedArticle, PublishResult | None]:
        article = self.generate()
        if dry_run:
            return article, None
        return article, self.csdn.publish(article)


def save_preview(article: GeneratedArticle, directory: str | Path = "output") -> Path:
    output_dir = Path(directory)
    output_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    safe_name = "".join(c for c in article.title if c not in r'\/:*?"<>|')[:40]
    path = output_dir / f"{timestamp}-{safe_name}.md"
    path.write_text(article.markdown, encoding="utf-8")
    return path


def write_result(result: PublishResult, path: str | Path = ".state/last_publish.json") -> None:
    state_path = Path(path)
    state_path.parent.mkdir(parents=True, exist_ok=True)
    data: dict[str, Any] = {
        "published_at": datetime.now().astimezone().isoformat(),
        "article_id": result.article_id,
        "title": result.title,
        "url": result.url,
        "message": result.message,
    }
    state_path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")

