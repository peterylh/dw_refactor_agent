#!/usr/bin/env python3
"""Initialize project-local business semantics catalogs."""

import argparse
import json
import os
import sys
from pathlib import Path

_src_root = Path(__file__).resolve().parents[2]
if str(_src_root) not in sys.path:
    sys.path.insert(0, str(_src_root))

from dw_refactor_agent.assessment.llm.model_metadata_writer import (
    run_catalog_discovery,  # noqa: E402
)
from dw_refactor_agent.assessment.project_facts.business_semantics import (  # noqa: E402
    write_initial_business_semantics_catalog,
)
from dw_refactor_agent.config import (  # noqa: E402
    PROJECT_CONFIG,
    TEXT_ENCODING,
)


def main() -> None:
    parser = argparse.ArgumentParser(description="初始化项目业务语义目录")
    parser.add_argument(
        "--project",
        default="shop",
        choices=list(PROJECT_CONFIG.keys()),
        help="项目名称",
    )
    parser.add_argument(
        "--overwrite",
        action="store_true",
        help="覆盖已存在的业务语义目录文件",
    )
    parser.add_argument(
        "--llm",
        action="store_true",
        help="调用表级 LLM 巡检结果初始化/更新目录",
    )
    parser.add_argument(
        "--model", default="deepseek-v4-flash", help="DeepSeek 模型名称"
    )
    parser.add_argument(
        "--max-retries",
        type=int,
        default=1,
        help="LLM 返回校验失败时的最大重试次数",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="忽略本地缓存，强制重新调用 API",
    )
    parser.add_argument(
        "--parallel", type=int, default=2, help="LLM 并发调用数，默认 2"
    )
    parser.add_argument(
        "--quiet", action="store_true", help="不打印单表巡检进度"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="只生成结果，不写文件"
    )
    parser.add_argument("--output", help="输出 JSON 文件路径")
    args = parser.parse_args()

    if args.llm:
        api_key = os.environ.get("DEEPSEEK_API_KEY")
        if not api_key:
            raise SystemExit(
                "未提供 DEEPSEEK_API_KEY 环境变量，无法调用 DeepSeek API"
            )
        result = run_catalog_discovery(
            args.project,
            api_key=api_key,
            model=args.model,
            max_retries=args.max_retries,
            parallelism=args.parallel,
            no_cache=args.no_cache,
            dry_run=args.dry_run,
            overwrite=args.overwrite,
            update_models=False,
            show_progress=not args.quiet,
        )
    else:
        result = write_initial_business_semantics_catalog(
            args.project,
            overwrite=args.overwrite,
            dry_run=args.dry_run,
        )
    if args.output:
        Path(args.output).write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding=TEXT_ENCODING,
        )
    catalog = result.get("catalog") or {}
    written_names = ", ".join(result.get("written_names") or []) or "-"
    print(
        "目录: {path}, 文件: {paths}, 本次写入: {written_names}, 来源: {source}, 业务过程: "
        "{process_count}, 语义主题: {subject_count}, 已写入: {updated}".format(
            path=result["path"],
            paths=", ".join(
                str(path) for path in (result.get("paths") or {}).values()
            )
            or "-",
            written_names=written_names,
            source=result.get("source", "programmatic"),
            process_count=len(catalog.get("business_processes") or []),
            subject_count=len(catalog.get("semantic_subjects") or []),
            updated=result["updated"],
        )
    )


if __name__ == "__main__":
    main()
