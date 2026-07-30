from __future__ import annotations

import json
import logging
import time
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from .config import Settings
from .service import PublishingService, save_preview, write_result

logger = logging.getLogger(__name__)
STATE_PATH = Path(".state/scheduler.json")


def _last_success(path: Path = STATE_PATH) -> datetime | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8")).get("last_success_at")
        return datetime.fromisoformat(value) if value else None
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        return None


def _mark_success(value: datetime, path: Path = STATE_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps({"last_success_at": value.isoformat()}, ensure_ascii=False),
        encoding="utf-8",
    )


def _is_due(now: datetime, last_success: datetime | None, interval_hours: float) -> bool:
    if interval_hours <= 0:
        raise ValueError("SCHEDULE_INTERVAL_HOURS 必须大于 0")
    if last_success is None:
        return True
    return now >= last_success + timedelta(hours=interval_hours)


def run_scheduler(settings: Settings) -> None:
    timezone = ZoneInfo(settings.schedule_timezone)
    interval_hours = settings.schedule_interval_hours
    if interval_hours <= 0:
        raise ValueError("SCHEDULE_INTERVAL_HOURS 必须大于 0")
    service = PublishingService(settings)
    logger.info(
        "定时器已启动：每次成功发布后间隔 %s 小时 (%s)",
        interval_hours,
        timezone,
    )

    while True:
        now = datetime.now(timezone)
        last_success = _last_success()
        if _is_due(now, last_success, interval_hours):
            try:
                article, result = service.run_once()
                save_preview(article)
                if result is None:
                    raise RuntimeError("发布结果为空")
                write_result(result)
                published_at = datetime.now(timezone)
                _mark_success(published_at)
                logger.info("发布成功：%s %s", result.title, result.url)
                logger.info(
                    "下次发布时间不早于：%s",
                    (published_at + timedelta(hours=interval_hours)).isoformat(),
                )
            except Exception:
                logger.exception("本次定时发布失败，5 分钟后将重试")
                time.sleep(300)
                continue
        time.sleep(20)
