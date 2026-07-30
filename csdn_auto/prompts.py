from __future__ import annotations

import json
import random
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path


BASE_SYSTEM_PROMPT = """你是一名资深 Java 技术作者和 Java 后端工程师，熟悉 Java 核心原理、JVM、并发编程、Spring Boot、数据库、微服务和工程化实践。请直接输出一篇可发布的中文 Markdown 技术文章，不要输出解释或代码围栏包裹全文。
硬性要求：
1. 第一行必须是唯一的一级标题（# 标题），标题具体、有搜索价值，不使用夸张营销词。
2. 正文 1800 到 2600 字，结构清晰，至少包含问题背景、方案设计、关键原理、完整示例、常见问题和总结。
3. Java 示例必须完整、可运行，注明必要的 JDK、框架或依赖版本，并解释关键步骤；不要编造 API、版本或测试结果。
4. 文章必须围绕给定业务场景解决一个具体问题，将抽取的技术点自然组合为一套合理方案，不能简单堆砌概念。
5. 明确说明方案适用边界、关键取舍和至少一个容易踩坑的细节。
6. 内容面向具有 Java 基础的开发者，不提及“AI 生成”、提示词、模型或本文生成过程。
7. 避免泛泛而谈和常见模板雷同，不虚构压测数据、生产事故或个人经历。
"""


DEFAULT_SCENES = (
    "电商订单在高并发下防止重复提交和重复扣款",
    "秒杀活动中控制瞬时流量并保证库存一致性",
    "用户中心在多服务之间同步账号状态",
    "支付回调出现乱序、重复和延迟时保证幂等",
    "大批量 Excel 或 CSV 数据导入时控制内存占用",
    "定时任务部署多个实例后避免重复执行",
    "微服务调用链过长时定位慢请求和异常",
    "热点数据访问量突然升高时保护数据库",
    "消息消费失败时实现可靠重试和死信处理",
    "文件上传与异步处理任务的进度管理",
    "多租户系统中的数据隔离和权限控制",
    "报表查询数据量增长后的性能优化",
    "配置变更需要在多个服务实例中实时生效",
    "数据库主从延迟导致读取旧数据时保证业务正确性",
    "第三方接口不稳定时控制重试和故障扩散",
)

DEFAULT_TECHNOLOGIES = (
    "Spring Boot 3",
    "Spring AOP",
    "Spring Transaction",
    "Java 21 虚拟线程",
    "CompletableFuture",
    "JUC 并发工具",
    "Redis",
    "Redis Lua 脚本",
    "MySQL 事务与锁",
    "MySQL 索引优化",
    "Kafka",
    "RabbitMQ",
    "Redisson",
    "Resilience4j",
    "Micrometer 与 Prometheus",
    "OpenTelemetry",
    "XXL-JOB",
    "Spring Batch",
    "Caffeine 本地缓存",
    "Jackson 流式解析",
    "JVM 内存与 GC",
    "Testcontainers",
)


@dataclass(frozen=True)
class PromptSelection:
    scenes: tuple[str, ...]
    technologies: tuple[str, ...]

    @property
    def combination_key(self) -> str:
        return json.dumps(
            {
                "scenes": sorted(self.scenes),
                "technologies": sorted(self.technologies),
            },
            ensure_ascii=False,
            sort_keys=True,
        )

    def user_prompt(self) -> str:
        scenes = "；".join(self.scenes)
        technologies = "、".join(self.technologies)
        return f"""生成今天要发布的一篇 Java 技术文章，只返回最终 Markdown。

本次随机选题素材：
- 业务场景：{scenes}
- 技术组合：{technologies}

先在内部判断这些技术在该场景中的合理分工，再选择一个具体问题作为文章主线。技术之间必须有真实的协作关系；如果某项技术不适合作为核心方案，可将它作为对比方案、观测手段或适用边界进行分析，但不能强行拼接。"""


class PromptComposer:
    def __init__(self, history_path: str | Path):
        self.history_path = Path(history_path)

    def choose(
        self,
        scene_count: int,
        tech_min: int,
        tech_max: int,
        recent_window: int,
    ) -> PromptSelection:
        if scene_count < 1 or len(DEFAULT_SCENES) < scene_count:
            raise ValueError("PROMPT_SCENE_COUNT 超出场景枚举数量")
        if (
            tech_min < 1
            or tech_max < tech_min
            or len(DEFAULT_TECHNOLOGIES) < tech_min
        ):
            raise ValueError("技术素材数量不足或抽取数量配置不正确")

        max_count = min(tech_max, len(DEFAULT_TECHNOLOGIES))
        recent_keys = self._recent_keys(recent_window)
        fallback: PromptSelection | None = None
        for _ in range(40):
            tech_count = random.randint(tech_min, max_count)
            selection = PromptSelection(
                scenes=tuple(random.sample(DEFAULT_SCENES, scene_count)),
                technologies=tuple(random.sample(DEFAULT_TECHNOLOGIES, tech_count)),
            )
            fallback = selection
            if selection.combination_key not in recent_keys:
                return selection
        if fallback is None:
            raise RuntimeError("无法生成提示词组合")
        return fallback

    def _recent_keys(self, limit: int) -> set[str]:
        if limit <= 0:
            return set()
        history = self._load_history()
        return {
            str(item["combination_key"])
            for item in history[-limit:]
            if "combination_key" in item
        }

    def record(self, selection: PromptSelection) -> None:
        history = self._load_history()
        history.append(
            {
                "combination_key": selection.combination_key,
                "scenes": list(selection.scenes),
                "technologies": list(selection.technologies),
                "created_at": datetime.now().astimezone().isoformat(),
            }
        )
        history = history[-200:]
        self.history_path.parent.mkdir(parents=True, exist_ok=True)
        temporary_path = self.history_path.with_suffix(
            self.history_path.suffix + ".tmp"
        )
        temporary_path.write_text(
            json.dumps({"history": history}, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
        temporary_path.replace(self.history_path)

    def _load_history(self) -> list[dict[str, object]]:
        if not self.history_path.exists():
            return []
        try:
            data = json.loads(self.history_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            raise RuntimeError(f"提示词历史文件格式错误：{self.history_path}") from exc
        history = data.get("history", [])
        if not isinstance(history, list):
            raise RuntimeError(f"提示词历史文件格式错误：{self.history_path}")
        return [item for item in history if isinstance(item, dict)]
