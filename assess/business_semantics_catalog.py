#!/usr/bin/env python3
"""Initialize project-local business semantics catalogs."""

import argparse
import json
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent
if str(_root) not in sys.path:
    sys.path.insert(0, str(_root))

from assess.project_facts.business_semantics import (  # noqa: E402
    write_initial_business_semantics_catalog,
)
from config import PROJECT_CONFIG  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(
        description="初始化项目 business_semantics.yaml 业务语义目录")
    parser.add_argument("--project",
                        default="shop",
                        choices=list(PROJECT_CONFIG.keys()),
                        help="项目名称")
    parser.add_argument("--overwrite",
                        action="store_true",
                        help="覆盖已存在的 business_semantics.yaml")
    parser.add_argument("--dry-run",
                        action="store_true",
                        help="只生成结果，不写文件")
    parser.add_argument("--output",
                        help="输出 JSON 文件路径")
    args = parser.parse_args()

    result = write_initial_business_semantics_catalog(
        args.project,
        overwrite=args.overwrite,
        dry_run=args.dry_run,
    )
    if args.output:
        Path(args.output).write_text(
            json.dumps(result, ensure_ascii=False, indent=2),
            encoding="utf-8",
        )
    print(
        "目录: {path}, 业务过程: {process_count}, 映射: {mapping_count}, "
        "已写入: {updated}".format(
            path=result["path"],
            process_count=len(
                (result.get("catalog") or {}).get("business_processes") or []
            ),
            mapping_count=len(
                (result.get("catalog") or {}).get("mappings") or []
            ),
            updated=result["updated"],
        )
    )


if __name__ == "__main__":
    main()
