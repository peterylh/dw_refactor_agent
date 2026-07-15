import importlib
import tempfile
from contextlib import ExitStack
from pathlib import Path

import pytest

import dw_refactor_agent.config as config


def _run_lock_module():
    return importlib.import_module("dw_refactor_agent.execution.run_lock")


def test_execution_target_lock_is_shared_across_checkouts(
    monkeypatch, tmp_path
):
    run_lock = _run_lock_module()
    monkeypatch.delenv("DW_REFACTOR_AGENT_RUN_LOCK_DIR", raising=False)
    checkout_a = tmp_path / "checkout-a"
    checkout_b = tmp_path / "checkout-b"

    monkeypatch.setattr(config.core, "PROJECT_ROOT", checkout_a)
    path_a = run_lock.execution_target_run_lock_path(
        " DORIS.EXAMPLE ",
        "09030",
        "`Demo_DB`",
    )
    monkeypatch.setattr(config.core, "PROJECT_ROOT", checkout_b)
    path_b = run_lock.execution_target_run_lock_path(
        "doris.example",
        9030,
        "demo_db",
    )

    assert path_a == path_b
    assert path_a.parent == (
        Path(tempfile.gettempdir()) / "dw_refactor_agent" / "run_locks"
    )
    assert path_a.name.startswith("demo_db-")
    assert path_a.suffix == ".lock"

    monkeypatch.setattr(config.core, "PROJECT_ROOT", checkout_a)
    with ExitStack() as stack:
        stack.enter_context(
            run_lock.execution_target_run_lock(
                "doris.example", 9030, "demo_db"
            )
        )
        monkeypatch.setattr(config.core, "PROJECT_ROOT", checkout_b)
        with ExitStack() as conflict_stack:
            conflict_stack.enter_context(
                pytest.raises(
                    run_lock.ExecutionRunLockError,
                    match="doris.example:9030/demo_db",
                )
            )
            conflict_stack.enter_context(
                run_lock.execution_target_run_lock(
                    "DORIS.EXAMPLE", "9030", "Demo_DB"
                )
            )


def test_execution_target_lock_directory_honors_environment_override(
    monkeypatch, tmp_path
):
    run_lock = _run_lock_module()
    override = tmp_path / "shared-locks"
    monkeypatch.setenv("DW_REFACTOR_AGENT_RUN_LOCK_DIR", str(override))

    lock_path = run_lock.execution_target_run_lock_path(
        "doris.example", 9030, "demo_db"
    )

    assert lock_path.parent == override


@pytest.mark.parametrize("override", [".locks", "foo/bar"])
def test_execution_target_lock_directory_rejects_relative_override(
    monkeypatch,
    override,
):
    run_lock = _run_lock_module()
    monkeypatch.setenv("DW_REFACTOR_AGENT_RUN_LOCK_DIR", override)

    with pytest.raises(
        ValueError,
        match=("DW_REFACTOR_AGENT_RUN_LOCK_DIR must be an absolute path"),
    ):
        run_lock.execution_target_run_lock_path(
            "doris.example", 9030, "demo_db"
        )
