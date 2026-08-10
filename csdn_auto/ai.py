from __future__ import annotations

import logging
import re
import time
from dataclasses import dataclass

import requests

from .config import Settings
from .prompts import BASE_SYSTEM_PROMPT, PromptComposer, revision_prompt
from .rag import (
    LocalKnowledgeBase,
    OpenAIEmbeddingProvider,
    PersistentVectorKnowledgeBase,
    format_context,
)

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
        documents = LocalKnowledgeBase(
            settings.rag_knowledge_dir,
            chunk_size=settings.rag_chunk_size,
            chunk_overlap=settings.rag_chunk_overlap,
        )
        if settings.rag_enabled and settings.rag_backend == "chroma":
            embedding_api_key = settings.embedding_api_key or settings.ai_api_key
            if not embedding_api_key:
                raise ValueError("启用 Chroma RAG 时必须配置 EMBEDDING_API_KEY")
            self.knowledge_base = PersistentVectorKnowledgeBase(
                documents=documents,
                embedding_provider=OpenAIEmbeddingProvider(
                    base_url=settings.embedding_base_url,
                    api_key=embedding_api_key,
                    model=settings.embedding_model,
                    timeout=settings.embedding_timeout,
                    dimensions=settings.embedding_dimensions,
                    failover_enabled=settings.embedding_failover_enabled,
                ),
                persist_directory=settings.rag_vector_path,
                collection_name=settings.rag_collection,
                batch_size=settings.rag_embedding_batch_size,
                query_instruction=settings.embedding_query_instruction,
                document_instruction=settings.embedding_document_instruction,
            )
        elif settings.rag_backend == "lexical" or not settings.rag_enabled:
            self.knowledge_base = documents
        else:
            raise ValueError("RAG_BACKEND 仅支持 chroma 或 lexical")

    def generate(self) -> GeneratedArticle:
        selection = self.prompts.choose(
            scene_count=self.settings.prompt_scene_count,
            tech_min=self.settings.prompt_tech_min,
            tech_max=self.settings.prompt_tech_max,
            recent_window=self.settings.prompt_recent_window,
        )
        chunks = (
            self.knowledge_base.retrieve(
                selection.retrieval_query,
                top_k=self.settings.rag_top_k,
            )
            if self.settings.rag_enabled
            else []
        )
        if self.settings.rag_backend == "chroma":
            chunks = [
                chunk
                for chunk in chunks
                if chunk.score >= self.settings.rag_min_score
            ]
        rag_context = format_context(chunks)
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
        if chunks:
            logger.info(
                "RAG(%s) 命中 %s 个片段：%s",
                self.settings.rag_backend,
                len(chunks),
                "、".join(chunk.source for chunk in chunks),
            )
        elif self.settings.rag_enabled:
            logger.info("RAG 未命中参考资料，将不带检索上下文生成")
        markdown_text = self._request_article(
            url,
            selection.user_prompt(rag_context),
            temperature=0.8,
        )
        issues = article_quality_issues(markdown_text, require_citations=bool(chunks))
        if issues:
            logger.warning("文章首稿未通过质检，将自动修订一次：%s", "；".join(issues))
            markdown_text = self._request_article(
                url,
                revision_prompt(markdown_text, issues, rag_context),
                temperature=0.3,
            )
            remaining_issues = article_quality_issues(
                markdown_text, require_citations=bool(chunks)
            )
            if remaining_issues:
                raise RuntimeError(
                    "文章自动修订后仍未通过发布质检："
                    + "；".join(remaining_issues)
                )
        article = parse_article(
            markdown_text,
            tags=",".join(("MCP", *selection.technologies[:4])),
        )
        self.prompts.record(selection)
        return article

    def _request_article(
        self, url: str, user_prompt: str, temperature: float
    ) -> str:
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
                        {"role": "user", "content": user_prompt},
                    ],
                    "temperature": temperature,
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
        return markdown_text

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


def article_quality_issues(
    markdown_text: str, require_citations: bool = False
) -> list[str]:
    """发布前做可确定性检查，把常见的模型幻觉拦在 CSDN 之前。"""
    text = markdown_text.strip()
    issues: list[str] = []
    title_match = re.match(r"^#\s+(.+?)\s*$", text, flags=re.M)
    title = title_match.group(1).strip() if title_match else ""
    if not title.startswith(("大厂 MCP 面试实录：", "MCP 高频面试题：", "MCP 模拟面试：")):
        issues.append("标题未使用约定的 MCP 面试型格式")
    if "模拟面试" not in text and "面试题复盘" not in text:
        issues.append("开头未明确声明是模拟面试或面试题复盘")
    for marker in ("面试官", "候选人", "考察点", "合格回答", "加分项"):
        if marker not in text:
            issues.append(f"缺少面试结构：{marker}")
    visible = re.sub(r"\s+", "", text)
    # Markdown 符号、代码与链接也会计入字符数，因此只拦截明显失控的长文。
    if len(visible) > 5000:
        issues.append(f"全文约 {len(visible)} 字符，明显超出 1800～2600 字的目标")
    if re.search(r"\d+(?:\.\d+)?\s*(?:%|％)", text):
        issues.append("包含无法自动核实的百分比")
    if re.search(r"(?:Java|Python|TypeScript)?\s*MCP\s*SDK\s*[vV]?\d+\.\d+", text):
        issues.append("包含具体 MCP SDK 版本，容易编造依赖或 API")
    if re.search(r"(?:knowledge/|imported/|\.state/chroma|[\w-]+-[0-9a-f]{8,}\.md)", text, flags=re.I):
        issues.append("向访客暴露了知识库内部路径或哈希文件名")
    if require_citations and not re.search(r"\[资料\d+\]", text):
        issues.append("使用了 RAG 参考资料，但正文没有 [资料1] 格式的事实引用")
    if require_citations and not re.search(r"^#{2,4}\s+参考资料\s*$", text, flags=re.M):
        issues.append("文末缺少规范的“参考资料”小节")
    return issues
