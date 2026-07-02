import ast

import config

PRODUCTION_PATHS = [
    "assess",
    "ddl_deriver",
    "exec",
    "finance_analytics",
    "lineage",
    "refact",
    "config",
]


def _production_python_files():
    for entry in PRODUCTION_PATHS:
        path = config.PROJECT_ROOT / entry
        if path.is_file():
            yield path
            continue
        for file_path in sorted(path.rglob("*.py")):
            yield file_path


def test_text_encoding_is_centralized_in_production_code():
    assert config.TEXT_ENCODING == "utf-8"

    violations = []
    for file_path in _production_python_files():
        tree = ast.parse(file_path.read_text(encoding=config.TEXT_ENCODING))
        for parent in ast.walk(tree):
            for child in ast.iter_child_nodes(parent):
                child.parent = parent
        for node in ast.walk(tree):
            if not isinstance(node, ast.Constant) or node.value != "utf-8":
                continue
            parent = getattr(node, "parent", None)
            if (
                file_path.name == "core.py"
                and isinstance(parent, ast.Assign)
                and any(
                    isinstance(target, ast.Name)
                    and target.id == "TEXT_ENCODING"
                    for target in parent.targets
                )
            ):
                continue
            if isinstance(parent, ast.keyword) and parent.arg == "encoding":
                violations.append(
                    f"{file_path.relative_to(config.PROJECT_ROOT)}:"
                    f"{node.lineno}"
                )
                continue
            if isinstance(parent, ast.Call):
                func = parent.func
                if isinstance(func, ast.Attribute) and func.attr in {
                    "encode",
                    "decode",
                }:
                    violations.append(
                        f"{file_path.relative_to(config.PROJECT_ROOT)}:"
                        f"{node.lineno}"
                    )
                    continue

    assert violations == []
