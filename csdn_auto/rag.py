from __future__ import annotations

import math
import re
from hashlib import sha256
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol
from urllib.parse import urlparse

import requests


SUPPORTED_SUFFIXES = {".md", ".markdown", ".txt"}


@dataclass(frozen=True)
class KnowledgeChunk:
    source: str
    content: str
    score: float = 0.0
    title: str = ""
    source_url: str = ""


def _tokens(text: str) -> list[str]:
    """Extract English terms and Chinese unigrams/bigrams for lexical retrieval."""
    normalized = text.lower()
    tokens = re.findall(r"[a-z][a-z0-9_.+-]{1,}|[\u4e00-\u9fff]", normalized)
    chinese = "".join(re.findall(r"[\u4e00-\u9fff]", normalized))
    tokens.extend(chinese[index : index + 2] for index in range(len(chinese) - 1))
    return tokens


class LocalKnowledgeBase:
    """Small dependency-free RAG store for Markdown and text documents."""

    def __init__(
        self,
        directory: str | Path,
        chunk_size: int = 1200,
        chunk_overlap: int = 150,
    ):
        self.directory = Path(directory)
        self.chunk_size = max(200, chunk_size)
        self.chunk_overlap = min(max(0, chunk_overlap), self.chunk_size // 2)

    def retrieve(self, query: str, top_k: int = 4) -> list[KnowledgeChunk]:
        if top_k <= 0:
            return []
        chunks = self._load_chunks()
        query_terms = Counter(_tokens(query))
        if not chunks or not query_terms:
            return []

        chunk_terms = [Counter(_tokens(chunk.content)) for chunk in chunks]
        document_frequency = Counter(
            term for terms in chunk_terms for term in terms.keys()
        )
        total = len(chunks)
        ranked: list[KnowledgeChunk] = []
        for chunk, terms in zip(chunks, chunk_terms):
            score = 0.0
            for term, query_frequency in query_terms.items():
                frequency = terms.get(term, 0)
                if not frequency:
                    continue
                inverse_frequency = math.log(
                    1 + (total - document_frequency[term] + 0.5)
                    / (document_frequency[term] + 0.5)
                )
                score += query_frequency * inverse_frequency * (
                    frequency / (frequency + 1.2)
                )
            if score > 0:
                ranked.append(
                    KnowledgeChunk(
                        chunk.source,
                        chunk.content,
                        round(score, 6),
                        chunk.title,
                        chunk.source_url,
                    )
                )
        ranked.sort(key=lambda item: item.score, reverse=True)
        return ranked[:top_k]

    def _load_chunks(self) -> list[KnowledgeChunk]:
        if not self.directory.is_dir():
            return []
        chunks: list[KnowledgeChunk] = []
        for path in sorted(self.directory.rglob("*")):
            if not path.is_file() or path.suffix.lower() not in SUPPORTED_SUFFIXES:
                continue
            text = path.read_text(encoding="utf-8").strip()
            if not text:
                continue
            source = str(path.relative_to(self.directory))
            title_match = re.search(r"^#\s+(.+?)\s*$", text, flags=re.M)
            title = title_match.group(1).strip() if title_match else path.stem
            source_match = re.match(r"^<!-- source: (.+?) -->", text)
            source_url = (
                _public_source_url(source_match.group(1).strip())
                if source_match
                else ""
            )
            title = _friendly_title(title, source_url or (source_match.group(1) if source_match else ""))
            chunks.extend(
                KnowledgeChunk(
                    source=source,
                    content=content,
                    title=title,
                    source_url=source_url,
                )
                for content in self._split(text)
            )
        return chunks

    def chunks(self) -> list[KnowledgeChunk]:
        """Return document chunks for vector indexing."""
        return self._load_chunks()

    def _split(self, text: str) -> list[str]:
        paragraphs = [item.strip() for item in re.split(r"\n\s*\n", text) if item.strip()]
        chunks: list[str] = []
        current = ""
        for paragraph in paragraphs:
            if current and len(current) + len(paragraph) + 2 > self.chunk_size:
                chunks.append(current)
                overlap = current[-self.chunk_overlap :] if self.chunk_overlap else ""
                current = f"{overlap}\n\n{paragraph}".strip()
            else:
                current = f"{current}\n\n{paragraph}".strip()
            while len(current) > self.chunk_size:
                chunks.append(current[: self.chunk_size])
                start = self.chunk_size - self.chunk_overlap
                current = current[start:]
        if current:
            chunks.append(current)
        return chunks


class EmbeddingProvider(Protocol):
    def embed(
        self, texts: list[str], instruction: str = ""
    ) -> list[list[float]]: ...


class OpenAIEmbeddingProvider:
    """Embedding client for OpenAI-compatible /embeddings endpoints."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        model: str,
        timeout: int = 60,
        dimensions: int | None = None,
        failover_enabled: bool = False,
        session: requests.Session | None = None,
    ):
        self.base_url = base_url.rstrip("/")
        self.api_key = api_key
        self.model = model
        self.timeout = timeout
        self.dimensions = dimensions
        self.failover_enabled = failover_enabled
        self.session = session or requests.Session()

    def embed(
        self, texts: list[str], instruction: str = ""
    ) -> list[list[float]]:
        if not texts:
            return []
        payload: dict[str, object] = {"model": self.model, "input": texts}
        if self.dimensions is not None:
            payload["dimensions"] = self.dimensions
        if instruction:
            payload["instruction"] = instruction
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        if self.failover_enabled:
            headers["X-Failover-Enabled"] = "true"
        try:
            response = self.session.post(
                f"{self.base_url}/embeddings",
                headers=headers,
                json=payload,
                timeout=self.timeout,
            )
            response.raise_for_status()
            data = response.json()["data"]
            ordered = sorted(data, key=lambda item: item["index"])
            embeddings = [item["embedding"] for item in ordered]
        except requests.HTTPError as exc:
            body = response.text[:2000].strip()
            raise RuntimeError(
                f"Embedding 请求失败：HTTP {response.status_code}，{body}"
            ) from exc
        except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
            raise RuntimeError(f"Embedding 请求失败：{exc}") from exc
        if len(embeddings) != len(texts):
            raise RuntimeError("Embedding 接口返回的向量数量与输入不一致")
        return embeddings


class PersistentVectorKnowledgeBase:
    """Chroma-backed knowledge base with incremental document synchronization."""

    def __init__(
        self,
        documents: LocalKnowledgeBase,
        embedding_provider: EmbeddingProvider,
        persist_directory: str | Path,
        collection_name: str = "csdn_mcp_knowledge",
        batch_size: int = 32,
        query_instruction: str = "",
        document_instruction: str = "",
        chroma_client: Any | None = None,
    ):
        self.documents = documents
        self.embedding_provider = embedding_provider
        self.batch_size = max(1, batch_size)
        self.query_instruction = query_instruction
        self.document_instruction = document_instruction
        if chroma_client is None:
            try:
                import chromadb
            except ImportError as exc:
                raise RuntimeError(
                    "未安装 Chroma，请先执行 pip install -r requirements.txt"
                ) from exc
            chroma_client = chromadb.PersistentClient(path=str(persist_directory))
        self.collection = chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"},
        )

    @staticmethod
    def _chunk_id(chunk: KnowledgeChunk) -> str:
        value = f"{chunk.source}\0{chunk.content}".encode("utf-8")
        return sha256(value).hexdigest()

    def sync(self) -> int:
        chunks = self.documents.chunks()
        desired = {self._chunk_id(chunk): chunk for chunk in chunks}
        stored_result = self.collection.get(include=["metadatas"])
        stored_ids = set(stored_result.get("ids", []))
        stored_metadatas = dict(
            zip(stored_result.get("ids", []), stored_result.get("metadatas", []))
        )
        desired_ids = set(desired)

        stale_ids = sorted(stored_ids - desired_ids)
        if stale_ids:
            self.collection.delete(ids=stale_ids)

        existing_ids = sorted(desired_ids & stored_ids)
        changed_metadata_ids = [
            item
            for item in existing_ids
            if stored_metadatas.get(item) != self._metadata(desired[item])
        ]
        for start in range(0, len(changed_metadata_ids), self.batch_size):
            ids = changed_metadata_ids[start : start + self.batch_size]
            self.collection.update(
                ids=ids,
                metadatas=[self._metadata(desired[item]) for item in ids],
            )

        new_ids = sorted(desired_ids - stored_ids)
        for start in range(0, len(new_ids), self.batch_size):
            ids = new_ids[start : start + self.batch_size]
            batch = [desired[item] for item in ids]
            texts = [item.content for item in batch]
            embeddings = self.embedding_provider.embed(
                texts, instruction=self.document_instruction
            )
            self.collection.upsert(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=[self._metadata(item) for item in batch],
            )
        return len(new_ids)

    @staticmethod
    def _metadata(chunk: KnowledgeChunk) -> dict[str, str]:
        metadata = {"source": chunk.source, "title": chunk.title or chunk.source}
        if chunk.source_url:
            metadata["source_url"] = chunk.source_url
        return metadata

    def retrieve(self, query: str, top_k: int = 4) -> list[KnowledgeChunk]:
        self.sync()
        count = self.collection.count()
        if top_k <= 0 or count == 0 or not query.strip():
            return []
        query_embedding = self.embedding_provider.embed(
            [query], instruction=self.query_instruction
        )[0]
        result = self.collection.query(
            query_embeddings=[query_embedding],
            n_results=min(top_k * 4, count),
            include=["documents", "metadatas", "distances"],
        )
        documents = (result.get("documents") or [[]])[0]
        metadatas = (result.get("metadatas") or [[]])[0]
        distances = (result.get("distances") or [[]])[0]
        candidates = [
            KnowledgeChunk(
                source=str(metadata.get("source", "unknown")),
                content=document,
                score=round(max(0.0, 1.0 - float(distance)), 6),
                title=str(metadata.get("title", "")),
                source_url=str(metadata.get("source_url", "")),
            )
            for document, metadata, distance in zip(
                documents, metadatas, distances
            )
        ]
        selected: list[KnowledgeChunk] = []
        selected_sources: set[str] = set()
        for candidate in candidates:
            if candidate.source in selected_sources:
                continue
            selected.append(candidate)
            selected_sources.add(candidate.source)
            if len(selected) == top_k:
                break
        return selected


def format_context(chunks: list[KnowledgeChunk]) -> str:
    if not chunks:
        return ""
    sections = []
    for index, chunk in enumerate(chunks, start=1):
        label = chunk.title or "未命名参考资料"
        source = f" | 公开链接: {chunk.source_url}" if chunk.source_url else ""
        public_content = re.sub(
            r"^<!-- (?:source|imported_at): .*? -->\s*",
            "",
            chunk.content,
            flags=re.M,
        ).strip()
        sections.append(f"[资料{index} | 标题: {label}{source}]\n{public_content}")
    return "\n\n".join(sections)


def _friendly_title(title: str, source: str) -> str:
    normalized = title.strip()
    if normalized.lower() == "overview":
        if "/basic/transports/" in source:
            return "MCP Transports Overview"
        if "/basic/" in source:
            return "MCP Protocol Overview and Schema"
    if normalized.lower() == "chroma":
        return "Chroma: Open-source Vector Database"
    return normalized


def _public_source_url(source: str) -> str:
    parsed = urlparse(source)
    if parsed.scheme not in {"http", "https"}:
        return ""
    if parsed.netloc != "raw.githubusercontent.com":
        return source
    parts = [item for item in parsed.path.split("/") if item]
    if len(parts) < 4:
        return source
    organization, repository = parts[0], parts[1]
    repository_path = parts[3:]
    if organization == "modelcontextprotocol" and repository == "modelcontextprotocol":
        if repository_path[:2] == ["docs", "specification"]:
            public_path = repository_path[1:]
        elif len(repository_path) >= 3 and repository_path[:2] == ["docs", "docs"]:
            public_path = ["docs", *repository_path[3:]]
        else:
            return "https://modelcontextprotocol.io"
        public_path[-1] = re.sub(r"\.mdx?$", "", public_path[-1])
        if public_path[-1] == "index":
            public_path.pop()
        return "https://modelcontextprotocol.io/" + "/".join(public_path)
    return f"https://github.com/{organization}/{repository}"
