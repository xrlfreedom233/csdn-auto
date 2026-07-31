from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

import requests

from .config import Settings
from .prompts import BASE_SYSTEM_PROMPT, PromptComposer

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class GeneratedArticle:
    title: str
    markdown: str
    description: str
    tags: str = ""


class AIClient:
    def __init__(self, settings: Settings, session: requests.Session | None = None):
        self.settings = settings
        self.session = session or requests.Session()
        self.prompts = PromptComposer(settings.prompt_history_path)

    def generate(self) -> GeneratedArticle:
        selection = self.prompts.choose(
            scene_count=self.settings.prompt_scene_count,
            tech_min=self.settings.prompt_tech_min,
            tech_max=self.settings.prompt_tech_max,
            recent_window=self.settings.prompt_recent_window,
        )
        url = f"{self.settings.ai_base_url}/chat/completions"
        logger.info(
            "随机选题：场景=%s；技术=%s",
            "；".join(selection.scenes),
            "、".join(selection.technologies),
        )
        logger.info(
            "正在请求 AI 生成文章：model=%s，最长等待=%s 秒",
            self.settings.ai_model,
            self.settings.ai_timeout,
        )
        started_at = time.monotonic()
        try:
            response = self.session.post(
                url,
                headers={
                    "Authorization": f"Bearer {self.settings.ai_api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": self.settings.ai_model,
                    "messages": [
                        {"role": "system", "content": BASE_SYSTEM_PROMPT},
                        {
                            "role": "user",
                            "content": selection.user_prompt(),
                        },
                    ],
                    "temperature": 0.8,
                },
                timeout=(
                    self.settings.ai_connect_timeout,
                    self.settings.ai_timeout,
                ),
            )
        except requests.exceptions.ConnectTimeout as exc:
            raise RuntimeError(
                f"连接 AI 接口超时（{self.settings.ai_connect_timeout} 秒）：{url}。"
                "请检查 AI_BASE_URL 和代理是否可用"
            ) from exc
        except requests.exceptions.ReadTimeout as exc:
            raise RuntimeError(
                f"AI 生成超过 {self.settings.ai_timeout} 秒。"
                "可增大 AI_TIMEOUT，或换用响应更快的模型"
            ) from exc
        except requests.exceptions.ProxyError as exc:
            raise RuntimeError(
                "无法连接系统代理。当前请求可能正在使用 HTTP_PROXY/HTTPS_PROXY，"
                "请确认代理程序已启动，或在运行前取消错误的代理环境变量"
            ) from exc
        except requests.exceptions.RequestException as exc:
            raise RuntimeError(f"AI 网络请求失败：{exc}") from exc

        logger.info("AI 已返回内容，耗时 %.1f 秒", time.monotonic() - started_at)
        self._raise_for_status(response)
        data = response.json()
        try:
            markdown_text = data["choices"][0]["message"]["content"].strip()
        except (KeyError, IndexError, TypeError, AttributeError) as exc:
            raise RuntimeError(f"AI 返回格式不正确：{data}") from exc
        article = parse_article(
            markdown_text,
            tags=",".join(selection.technologies[:5]),
        )
        self.prompts.record(selection)
        return article

    @staticmethod
    def _raise_for_status(response: requests.Response) -> None:
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            body = response.text[:1000]
            raise RuntimeError(f"AI 请求失败：HTTP {response.status_code}，{body}") from exc


def parse_article(markdown_text: str, tags: str = "") -> GeneratedArticle:
    text = re.sub(r"^```(?:markdown|md)?\s*", "", markdown_text.strip(), flags=re.I)
    text = re.sub(r"\s*```$", "", text).strip()
    match = re.match(r"^#\s+(.+?)\s*$", text, flags=re.M)
    if not match:
        raise ValueError("AI 内容缺少第一行一级标题")

    title = re.sub(r"\s+#*$", "", match.group(1)).strip()
    if not title:
        raise ValueError("AI 生成的标题为空")
    body = text[match.end() :].lstrip()
    clean_text = re.sub(r"[#>*_`\-\[\]()]", " ", body)
    clean_text = re.sub(r"\s+", " ", clean_text).strip()
    description = clean_text[:120].rstrip("，,。；; ") + "。"
    return GeneratedArticle(
        title=title[:100],
        markdown=text,
        description=description[:200],
        tags=tags,
    )
