from __future__ import annotations

import argparse
import json
import logging
import sys

from .config import Settings
from .importer import KnowledgeImporter
from .scheduler import run_scheduler
from .service import PublishingService, save_preview, write_result


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="AI 自动生成并发布 CSDN 文章")
    subparsers = parser.add_subparsers(dest="command", required=True)

    publish = subparsers.add_parser("publish", help="立即生成并发布一篇文章")
    publish.add_argument(
        "--dry-run",
        action="store_true",
        help="只生成并保存 Markdown，不调用 CSDN",
    )
    subparsers.add_parser("schedule", help="启动间隔定时任务")
    knowledge_import = subparsers.add_parser(
        "import-knowledge", help="清洗网页或本地文档并导入 RAG 知识库"
    )
    knowledge_import.add_argument(
        "sources",
        nargs="+",
        help="网页 URL、PDF、DOCX、HTML、Markdown、TXT 文件或目录",
    )
    knowledge_import.add_argument(
        "--output-dir",
        default="knowledge/imported",
        help="清洗后 Markdown 的保存目录",
    )
    knowledge_import.add_argument(
        "--timeout", type=int, default=30, help="网页下载超时秒数"
    )
    knowledge_import.add_argument(
        "--max-mb", type=int, default=25, help="单个文档的最大 MB 数"
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(message)s",
    )
    args = build_parser().parse_args(argv)
    try:
        if args.command == "import-knowledge":
            importer = KnowledgeImporter(
                output_directory=args.output_dir,
                timeout=args.timeout,
                max_bytes=args.max_mb * 1024 * 1024,
            )
            results = importer.import_many(args.sources)
            print(
                json.dumps(
                    {
                        "imported": len(results),
                        "documents": [
                            {
                                "source": result.source,
                                "title": result.title,
                                "characters": result.characters,
                                "output": str(result.output_path),
                            }
                            for result in results
                        ],
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
            return 0
        settings = Settings.from_env()
        if args.command == "schedule":
            run_scheduler(settings)
            return 0

        service = PublishingService(settings)
        if service.csdn.uses_static_signature and not args.dry_run:
            logging.warning("正在使用抓包中的静态 CSDN 签名，它可能因过期或防重放而失败")
        article, result = service.run_once(dry_run=args.dry_run)
        preview_path = save_preview(article)
        if result is None:
            print(
                json.dumps(
                    {
                        "dry_run": True,
                        "title": article.title,
                        "preview": str(preview_path),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        else:
            write_result(result)
            print(
                json.dumps(
                    {
                        "article_id": result.article_id,
                        "title": result.title,
                        "url": result.url,
                        "message": result.message,
                        "preview": str(preview_path),
                    },
                    ensure_ascii=False,
                    indent=2,
                )
            )
        return 0
    except KeyboardInterrupt:
        return 130
    except Exception as exc:
        logging.error("%s", exc)
        return 1


if __name__ == "__main__":
    sys.exit(main())
