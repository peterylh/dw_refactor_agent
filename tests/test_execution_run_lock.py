import importlib
from contextlib import ExitStack

import pytest

import dw_refactor_agent.config as config


def _run_lock_module():
    return importlib.import_module("dw_refactor_agent.execution.run_lock")


def _configure_project(monkeypatch, tmp_path, name):
    monkeypatch.setattr(config.core, "PROJECT_ROOT", tmp_path)
    monkeypatch.setitem(
        config.PROJECT_CONFIG,
        name,
        {"dir": name, "db": "{}_dm".format(name)},
    )


def test_project_run_lock_is_nonblocking_and_os_released(
    monkeypatch, tmp_path
):
    run_lock = _run_lock_module()
    _configure_project(monkeypatch, tmp_path, "demo")

    assert run_lock.project_run_lock_path("demo") == (
        tmp_path / "demo/artifacts/execution/task_run.lock"
    )
    with ExitStack() as stack:
        stack.enter_context(run_lock.project_run_lock("demo"))
        stack.enter_context(
            pytest.raises(
                run_lock.ProjectRunLockError,
                match="another task_run SQL execution is active.*demo",
            )
        )
        stack.enter_context(run_lock.project_run_lock("demo"))

    with run_lock.project_run_lock("demo"):
        pass


def test_project_run_lock_allows_different_projects(monkeypatch, tmp_path):
    run_lock = _run_lock_module()
    _configure_project(monkeypatch, tmp_path, "alpha")
    _configure_project(monkeypatch, tmp_path, "beta")

    with ExitStack() as stack:
        stack.enter_context(run_lock.project_run_lock("alpha"))
        stack.enter_context(run_lock.project_run_lock("beta"))
