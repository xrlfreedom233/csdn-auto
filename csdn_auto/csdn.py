from __future__ import annotations

import base64
import hashlib
import hmac
import uuid
from dataclasses import dataclass
from typing import Any

import markdown as markdown_lib
import requests

from .ai import GeneratedArticle
from .config import Settings


SAVE_URL = "https://bizapi.csdn.net/blog-console-api/v1/postedit/saveArticle"
SAVE_PATH = "/blog-console-api/v1/postedit/saveArticle"
ACCEPT = "application/json, text/plain, */*"
CONTENT_TYPE = "application/json;"


@dataclass(frozen=True)
class PublishResult:
    article_id: int | str
    title: str
    url: str
    message: str


class CSDNClient:
    def __init__(self, settings: Settings, session: requests.Session | None = None):
        self.settings = settings
        self.session = session or requests.Session()

    @property
    def uses_static_signature(self) -> bool:
        return not bool(self.settings.csdn_x_ca_secret)

    def _signature_headers(self) -> dict[str, str]:
        key = self.settings.csdn_x_ca_key
        if self.settings.csdn_x_ca_secret:
            nonce = str(uuid.uuid4())
            signature = make_signature(
                secret=self.settings.csdn_x_ca_secret,
                key=key,
                nonce=nonce,
            )
        else:
            nonce = self.settings.csdn_x_ca_nonce
            signature = self.settings.csdn_x_ca_signature
            if not nonce or not signature:
                raise ValueError(
                    "缺少 CSDN 签名配置：请提供 CSDN_X_CA_SECRET，"
                    "或临时提供 CSDN_X_CA_NONCE 和 CSDN_X_CA_SIGNATURE"
                )
        return {
            "x-ca-key": key,
            "x-ca-nonce": nonce,
            "x-ca-signature": signature,
            "x-ca-signature-headers": "x-ca-key,x-ca-nonce",
            "x-ca-stage": "",
        }

    def build_payload(self, article: GeneratedArticle) -> dict[str, Any]:
        html = markdown_lib.markdown(
            article.markdown,
            extensions=["fenced_code", "tables", "sane_lists"],
        )
        return {
            "article_id": self.settings.csdn_article_id,
            "title": article.title,
            "description": article.description,
            "content": html,
            "markdowncontent": article.markdown,
            "tags": article.tags or self.settings.csdn_tags,
            "categories": self.settings.csdn_category,
            "type": "original",
            "status": 0,
            "read_type": "public",
            "editor_type": 1,
            "source": "pc_postedit",
            "is_new": 1,
            "not_auto_saved": 1,
            "authorized_status": False,
            "check_original": False,
            "cover_images": [],
            "cover_type": 1,
            "creation_statement": 0,
            "creator_activity_id": "",
            "level": "0",
            "original_link": "",
            "plan": [],
            "reason": "",
            "resource_id": "",
            "resource_url": "",
            "scheduled_time": 0,
            "strategy": None,
            "sync_git_code": 0,
            "vote_id": 0,
        }

    def publish(self, article: GeneratedArticle) -> PublishResult:
        headers = {
            "Accept": ACCEPT,
            "Content-Type": CONTENT_TYPE,
            "Cookie": self.settings.csdn_cookie,
            "Origin": "https://mp.csdn.net",
            "Referer": "https://mp.csdn.net/",
            "User-Agent": (
                "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
                "(KHTML, like Gecko) Chrome/150.0.0.0 Safari/537.36"
            ),
            **self._signature_headers(),
        }
        response = self.session.post(
            SAVE_URL,
            headers=headers,
            json=self.build_payload(article),
            timeout=60,
        )
        try:
            response.raise_for_status()
        except requests.HTTPError as exc:
            raise RuntimeError(
                f"CSDN 请求失败：HTTP {response.status_code}，{response.text[:1000]}"
            ) from exc

        try:
            data = response.json()
        except requests.JSONDecodeError as exc:
            raise RuntimeError(f"CSDN 返回的不是 JSON：{response.text[:1000]}") from exc
        if data.get("code") != 200:
            raise RuntimeError(f"CSDN 发布失败：{data}")

        result = data.get("data") or {}
        return PublishResult(
            article_id=result.get("article_id", ""),
            title=result.get("title", article.title),
            url=result.get("url", ""),
            message=data.get("msg", "发布成功"),
        )


def make_signature(secret: str, key: str, nonce: str) -> str:
    """按 CSDN 当前使用的 API Gateway 规范生成 HMAC-SHA256 签名。"""
    canonical_headers = f"x-ca-key:{key}\nx-ca-nonce:{nonce}\n"
    string_to_sign = (
        f"POST\n{ACCEPT}\n\n{CONTENT_TYPE}\n\n"
        f"{canonical_headers}{SAVE_PATH}"
    )
    digest = hmac.new(
        secret.encode("utf-8"),
        string_to_sign.encode("utf-8"),
        hashlib.sha256,
    ).digest()
    return base64.b64encode(digest).decode("ascii")
