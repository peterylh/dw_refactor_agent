import importlib.util
import os
import sys


def _parse_version(version_text):
    return tuple(int(part) for part in version_text.split(".") if part)


def _is_under_path(child, parent):
    child = os.path.realpath(child)
    parent = os.path.realpath(parent)
    try:
        return os.path.commonpath([child, parent]) == parent
    except ValueError:
        return False


def _conda_prefix_status():
    expected_env = os.environ.get("EXPECTED_CONDA_ENV")
    conda_env = os.environ.get("CONDA_DEFAULT_ENV")
    conda_prefix = os.environ.get("CONDA_PREFIX")

    if not expected_env or not conda_prefix or conda_env != expected_env:
        return "skipped", True

    executable_ok = _is_under_path(sys.executable, conda_prefix)
    prefix_ok = _is_under_path(sys.prefix, conda_prefix)
    if executable_ok and prefix_ok:
        return "ok", True
    return "mismatch", False


def main():
    expected_version_text = os.environ.get("REQUIRED_PYTHON_VERSION", "3.7")
    expected_version = _parse_version(expected_version_text)
    required_modules = os.environ.get("REQUIRED_PYTHON_MODULES", "").split()
    missing_modules = [
        name
        for name in required_modules
        if importlib.util.find_spec(name) is None
    ]
    prefix_status, prefix_ok = _conda_prefix_status()
    version_ok = sys.version_info[: len(expected_version)] == expected_version

    print("python:", sys.executable)
    print("prefix:", sys.prefix)
    print("version:", sys.version.split()[0])
    print("expected:", expected_version_text)
    print(
        "modules:",
        "ok"
        if not missing_modules
        else "missing " + ", ".join(missing_modules),
    )
    print("conda env:", os.environ.get("CONDA_DEFAULT_ENV", "(unset)"))
    print("conda prefix:", os.environ.get("CONDA_PREFIX", "(unset)"))
    print("conda prefix match:", prefix_status)

    return 0 if version_ok and not missing_modules and prefix_ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
