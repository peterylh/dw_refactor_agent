import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_CODE_DIRS = (
    "config",
    "assess",
    "ddl_deriver",
    "exec",
    "finance_analytics",
    "lineage",
    "refact",
)
ROOT_MODULES = ("doris_sql.py",)


def _project_python_files():
    files = [PROJECT_ROOT / name for name in ROOT_MODULES]
    for dirname in PROJECT_CODE_DIRS:
        files.extend(sorted((PROJECT_ROOT / dirname).rglob("*.py")))
    return [
        path
        for path in files
        if path.exists() and ".conda-py37" not in path.parts
    ]


def test_project_modules_import_under_python37_with_released_sqlglot():
    if sys.version_info[:2] != (3, 7):
        pytest.skip("Python 3.7 compatibility gate runs in the py37 env")

    script = textwrap.dedent(
        """
        import importlib
        import importlib.util
        import json
        from pathlib import Path
        import re
        import sqlglot
        import sys

        sqlglot_path = Path(sqlglot.__file__).resolve()
        if sqlglot.__version__ != "26.9.0":
            raise AssertionError(
                "expected sqlglot 26.9.0, got %s from %s"
                % (sqlglot.__version__, sqlglot_path)
            )
        if str(sqlglot_path).startswith("/Users/yulihua/Projects/sqlglot"):
            raise AssertionError("local sqlglot checkout is not allowed: %s" % sqlglot_path)

        module_paths = json.loads(sys.argv[1])
        sys.argv = [sys.argv[0]]

        failures = []
        for raw_path in module_paths:
            path = Path(raw_path)
            try:
                rel = path.relative_to(Path.cwd())
                if rel.parts[0] == "config":
                    if path.name == "__init__.py":
                        module_name = ".".join(rel.parts[:-1])
                    else:
                        module_name = ".".join(rel.with_suffix("").parts)
                    importlib.import_module(module_name)
                else:
                    module_name = "compat_" + re.sub(r"[^0-9A-Za-z_]", "_", str(path))
                    spec = importlib.util.spec_from_file_location(module_name, str(path))
                    module = importlib.util.module_from_spec(spec)
                    sys.modules[module_name] = module
                    spec.loader.exec_module(module)
            except Exception as exc:
                failures.append("%s: %s: %s" % (path, type(exc).__name__, exc))

        if failures:
            raise AssertionError("\\n".join(failures))
        """
    )

    env = os.environ.copy()
    env.pop("PYTHONPATH", None)
    result = subprocess.run(
        [
            sys.executable,
            "-c",
            script,
            json.dumps([str(p) for p in _project_python_files()]),
        ],
        cwd=str(PROJECT_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
