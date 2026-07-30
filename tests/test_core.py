from __future__ import annotations

import unittest
from datetime import datetime, timedelta, timezone
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import Mock

import requests

from csdn_auto.ai import AIClient, GeneratedArticle, parse_article
from csdn_auto.config import Settings
from csdn_auto.csdn import CSDNClient
from csdn_auto.prompts import PromptComposer
from csdn_auto.scheduler import _is_due, _last_success, _mark_success


def settings() -> Settings:
    return Settings(
        ai_base_url="https://example.test/v1",
        ai_api_key="test",
        ai_model="test",
        ai_connect_timeout=5,
        ai_timeout=10,
        csdn_cookie="SESSION=test",
        csdn_x_ca_key="203803574",
        csdn_x_ca_secret="secret",
        csdn_x_ca_nonce="",
        csdn_x_ca_signature="",
        csdn_article_id="",
        csdn_tags="python",
        csdn_category="",
        prompt_history_path="/tmp/csdn_auto-test-prompt-history.json",
        prompt_scene_count=1,
        prompt_tech_min=2,
        prompt_tech_max=3,
        prompt_recent_window=30,
        schedule_interval_hours=6,
        schedule_timezone="Asia/Shanghai",
    )


class ParseArticleTests(unittest.TestCase):
    def test_parses_title_and_description(self) -> None:
        article = parse_article("# Python 定时任务\n\n这是正文内容，用于测试描述生成。")
        self.assertEqual(article.title, "Python 定时任务")
        self.assertTrue(article.description.startswith("这是正文内容"))

    def test_rejects_missing_title(self) -> None:
        with self.assertRaises(ValueError):
            parse_article("没有一级标题")


class AIClientTests(unittest.TestCase):
    def test_reports_proxy_error(self) -> None:
        session = Mock()
        session.post.side_effect = requests.exceptions.ProxyError("proxy unavailable")
        client = AIClient(settings(), session=session)
        with self.assertRaisesRegex(RuntimeError, "无法连接系统代理"):
            client.generate()


class PromptComposerTests(unittest.TestCase):
    def test_combines_enumerated_items_and_records_json_history(self) -> None:
        with TemporaryDirectory() as directory:
            composer = PromptComposer(Path(directory) / "prompt_history.json")
            selection = composer.choose(1, 2, 3, 30)
            self.assertEqual(len(selection.scenes), 1)
            self.assertGreaterEqual(len(selection.technologies), 2)
            self.assertIn("业务场景", selection.user_prompt())
            composer.record(selection)
            self.assertIn(selection.combination_key, composer._recent_keys(30))
            self.assertTrue((Path(directory) / "prompt_history.json").exists())


class SchedulerTests(unittest.TestCase):
    def test_first_run_is_due_and_then_waits_six_hours(self) -> None:
        now = datetime(2026, 7, 30, 9, 0, tzinfo=timezone.utc)
        self.assertTrue(_is_due(now, None, 6))
        self.assertFalse(_is_due(now + timedelta(hours=5, minutes=59), now, 6))
        self.assertTrue(_is_due(now + timedelta(hours=6), now, 6))

    def test_persists_last_success(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "scheduler.json"
            published_at = datetime(2026, 7, 30, 9, 0, tzinfo=timezone.utc)
            _mark_success(published_at, path)
            self.assertEqual(_last_success(path), published_at)


class CSDNClientTests(unittest.TestCase):
    def test_payload_contains_markdown_and_html(self) -> None:
        client = CSDNClient(settings())
        payload = client.build_payload(
            GeneratedArticle(
                title="测试",
                markdown="# 测试\n\n```python\nprint('ok')\n```",
                description="描述。",
            )
        )
        self.assertEqual(payload["markdowncontent"], "# 测试\n\n```python\nprint('ok')\n```")
        self.assertIn("<code", payload["content"])
        self.assertEqual(payload["status"], 0)

    def test_publish_checks_business_code(self) -> None:
        session = Mock()
        response = Mock()
        response.raise_for_status.return_value = None
        response.json.return_value = {"code": 401, "msg": "未登录"}
        session.post.return_value = response
        client = CSDNClient(settings(), session=session)
        with self.assertRaisesRegex(RuntimeError, "发布失败"):
            client.publish(
                GeneratedArticle(title="标题", markdown="# 标题\n\n正文", description="正文。")
            )


if __name__ == "__main__":
    unittest.main()
