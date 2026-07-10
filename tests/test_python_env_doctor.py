import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCTOR_SCRIPT = REPO_ROOT / "scripts" / "python_env_doctor.py"
CURRENT_VERSION = "{}.{}".format(*sys.version_info[:2])


def _run_doctor(env_overrides):
    env = os.environ.copy()
    env.update(
        {
            "REQUIRED_PYTHON_VERSION": CURRENT_VERSION,
            "REQUIRED_PYTHON_MODULES": "",
        }
    )
    env.update(env_overrides)
    return subprocess.run(
        [sys.executable, str(DOCTOR_SCRIPT)],
        cwd=str(REPO_ROOT),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )


def test_python_env_doctor_rejects_mismatched_target_conda_prefix(tmp_path):
    result = _run_doctor(
        {
            "CONDA_DEFAULT_ENV": "fake-env",
            "CONDA_PREFIX": str(tmp_path / "fake-env"),
            "EXPECTED_CONDA_ENV": "fake-env",
        }
    )

    assert result.returncode == 1
    assert "conda prefix match: mismatch" in result.stdout


def test_python_env_doctor_allows_explicit_non_conda_python_override(tmp_path):
    result = _run_doctor(
        {
            "CONDA_DEFAULT_ENV": "active-shell-env",
            "CONDA_PREFIX": str(tmp_path / "active-shell-env"),
            "EXPECTED_CONDA_ENV": "fake-env",
        }
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "conda prefix match: skipped" in result.stdout
