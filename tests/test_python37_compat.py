import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parents[1]
PROJECT_CODE_DIRS = (
    "src/dw_refactor_agent",
    "warehouses/finance_analytics",
)
ROOT_MODULES = ()
SQLGLOT_FORK_URL = "https://github.com/HYDCP/hy-sqlglot.git"
SQLGLOT_FORK_COMMIT = "77fe22e66498ea4ad996d9c5a172c69d7ac693c8"
SQLGLOT_FORK_REF = f"git+{SQLGLOT_FORK_URL}@{SQLGLOT_FORK_COMMIT}"


def _project_python_files():
    files = [PROJECT_ROOT / name for name in ROOT_MODULES]
    for dirname in PROJECT_CODE_DIRS:
        files.extend(sorted((PROJECT_ROOT / dirname).rglob("*.py")))
    return [
        path
        for path in files
        if path.exists() and ".conda-py37" not in path.parts
    ]


def test_project_uses_doris_sqlglot_fork_under_python37():
    for manifest in (
        "Makefile",
        "environment-py37.yml",
        "pyproject.toml",
        "docs/python37_development.md",
    ):
        manifest_text = (PROJECT_ROOT / manifest).read_text(encoding="utf-8")
        assert SQLGLOT_FORK_COMMIT in manifest_text, manifest
        if manifest != "docs/python37_development.md":
            assert SQLGLOT_FORK_REF in manifest_text, manifest

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

        src_root = Path.cwd() / "src"
        if str(src_root) not in sys.path:
            sys.path.insert(0, str(src_root))

        sqlglot_path = Path(sqlglot.__file__).resolve()
        if not sqlglot.__version__.startswith("26.9."):
            raise AssertionError(
                "expected sqlglot 26.9.x, got %s from %s"
                % (sqlglot.__version__, sqlglot_path)
            )
        direct_url_paths = list(
            sqlglot_path.parent.parent.glob("sqlglot-*.dist-info/direct_url.json")
        )
        if len(direct_url_paths) != 1:
            raise AssertionError(
                "expected one sqlglot direct_url.json, got %s"
                % direct_url_paths
            )
        direct_url = json.loads(direct_url_paths[0].read_text(encoding="utf-8"))
        vcs_info = direct_url.get("vcs_info") or {}
        if direct_url.get("url") != "https://github.com/HYDCP/hy-sqlglot.git":
            raise AssertionError("unexpected sqlglot source: %s" % direct_url)
        if vcs_info.get("commit_id") != "77fe22e66498ea4ad996d9c5a172c69d7ac693c8":
            raise AssertionError("unexpected sqlglot commit: %s" % direct_url)
        if str(sqlglot_path).startswith("/Users/yulihua/Projects/sqlglot"):
            raise AssertionError("local sqlglot checkout is not allowed: %s" % sqlglot_path)

        module_paths = json.loads(sys.argv[1])
        sys.argv = [sys.argv[0]]

        failures = []
        for raw_path in module_paths:
            path = Path(raw_path)
            try:
                rel = path.relative_to(Path.cwd())
                if rel.parts[:2] == ("src", "dw_refactor_agent"):
                    if path.name == "__init__.py":
                        module_name = ".".join(rel.parts[1:-1])
                    else:
                        module_name = ".".join(
                            rel.with_suffix("").parts[1:]
                        )
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
