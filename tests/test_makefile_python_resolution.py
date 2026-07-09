import os
import stat
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]


def _write_executable(path, text):
    path.write_text(text)
    path.chmod(path.stat().st_mode | stat.S_IXUSR)


def test_makefile_python_uses_conda_prefix_before_path_python(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_shims = tmp_path / "pyenv-shims"
    fake_env = tmp_path / "conda-env"
    fake_env_bin = fake_env / "bin"
    marker = tmp_path / "python-marker.txt"

    fake_bin.mkdir()
    fake_shims.mkdir()
    fake_env_bin.mkdir(parents=True)

    _write_executable(
        fake_bin / "conda",
        """#!/bin/sh
if [ "$1" != "run" ]; then
  exit 64
fi
shift
if [ "$1" != "-n" ]; then
  exit 65
fi
shift 2
export CONDA_PREFIX="$FAKE_CONDA_PREFIX"
export CONDA_DEFAULT_ENV="fake-env"
exec "$@"
""",
    )
    _write_executable(
        fake_shims / "python",
        """#!/bin/sh
printf 'shim-python\\n' > "$FAKE_PYTHON_MARKER"
exit 86
""",
    )
    _write_executable(
        fake_env_bin / "python",
        """#!/bin/sh
printf 'conda-env-python\\n' > "$FAKE_PYTHON_MARKER"
exit 0
""",
    )

    env = os.environ.copy()
    for name in ("MAKEFLAGS", "MFLAGS", "MAKELEVEL", "PYTHON"):
        env.pop(name, None)
    env.update(
        {
            "FAKE_CONDA_PREFIX": str(fake_env),
            "FAKE_PYTHON_MARKER": str(marker),
            "PATH": os.pathsep.join(
                [
                    str(fake_bin),
                    str(fake_shims),
                    str(fake_env_bin),
                    env["PATH"],
                ]
            ),
        }
    )

    result = subprocess.run(
        [
            "make",
            "doctor",
            "CONDA=conda",
            "CONDA_ENV=fake-env",
            "REQUIRED_PYTHON_VERSION={}.{}".format(*sys.version_info[:2]),
            "REQUIRED_PYTHON_MODULES=",
        ],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert marker.read_text().strip() == "conda-env-python"


def test_env_update_installs_pip_packages_with_conda_prefix_python(tmp_path):
    fake_bin = tmp_path / "bin"
    fake_env = tmp_path / "conda-env"
    fake_env_bin = fake_env / "bin"
    marker = tmp_path / "python-marker.txt"
    custom_python = tmp_path / "custom-python"

    fake_bin.mkdir()
    fake_env_bin.mkdir(parents=True)

    _write_executable(
        fake_bin / "conda",
        """#!/bin/sh
case "$1" in
  install)
    exit 0
    ;;
  run)
    shift
    if [ "$1" != "-n" ]; then
      exit 65
    fi
    shift 2
    export CONDA_PREFIX="$FAKE_CONDA_PREFIX"
    export CONDA_DEFAULT_ENV="fake-env"
    exec "$@"
    ;;
  *)
    exit 64
    ;;
esac
""",
    )
    _write_executable(
        fake_env_bin / "python",
        """#!/bin/sh
printf 'conda-env-python %s\\n' "$*" >> "$FAKE_PYTHON_MARKER"
exit 0
""",
    )
    _write_executable(
        custom_python,
        """#!/bin/sh
printf 'custom-python\\n' >> "$FAKE_PYTHON_MARKER"
exit 87
""",
    )

    env = os.environ.copy()
    for name in ("MAKEFLAGS", "MFLAGS", "MAKELEVEL"):
        env.pop(name, None)
    env.update(
        {
            "FAKE_CONDA_PREFIX": str(fake_env),
            "FAKE_PYTHON_MARKER": str(marker),
            "PATH": os.pathsep.join([str(fake_bin), env["PATH"]]),
        }
    )

    result = subprocess.run(
        [
            "make",
            "env-update",
            "CONDA=conda",
            "CONDA_ENV=fake-env",
            "PYTHON={}".format(custom_python),
        ],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    marker_lines = marker.read_text().splitlines()
    assert len(marker_lines) == 3
    assert all(
        line.startswith("conda-env-python -m pip") for line in marker_lines
    )
