"""Shared task execution planner for direct and shadow runs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

import dw_refactor_agent.config as config
from dw_refactor_agent.execution.invocation import TaskInvocation
from dw_refactor_agent.execution.model_config import (
    ExecutionConfigError,
    SliceConfig,
    execution_config_for_model,
    normalize_materialized,
    normalize_strategy,
    slice_config_from_mapping,
)


@dataclass(frozen=True)
class TaskSpec:
    job_name: str
    sql_path: Path
    materialized: str
    full_refresh_strategy: str
    slice_param: str | None
    slice_column: str | None
    slice_period: str | None
    companion_path: Path | None
    historical_replay_supported: bool


class ExecutionPlanner:
    """Create task invocations from warehouse/model execution config."""

    def __init__(self, project: str, project_root: Path | None = None):
        self.project = project
        self.project_root = Path(project_root or config.core.PROJECT_ROOT)
        self.project_config = self._project_config()
        self.project_dir = self._project_dir()
        self.warehouse_execution = self._warehouse_execution_config()
        self.model_metadata = self._load_model_metadata()

    def task_spec(self, job_name: str, sql_path: Path) -> TaskSpec:
        raw_model = self.model_metadata.get(job_name, {})
        raw_execution = execution_config_for_model(job_name, raw_model)

        materialized = normalize_materialized(
            job_name,
            raw_execution.get("materialized", "incremental"),
        )
        strategy = normalize_strategy(
            job_name,
            materialized,
            raw_execution.get("full_refresh_strategy"),
        )
        # Full models do not consume the warehouse default slice.  Reject an
        # explicit model slice instead of silently accepting contradictory
        # execution metadata.
        if materialized == "full":
            explicit_slice = slice_config_from_mapping(
                job_name,
                raw_execution.get("slice"),
                label="execution.slice",
            )
            if explicit_slice is not None:
                raise ExecutionConfigError(
                    f"[{job_name}] full models cannot define execution.slice"
                )
            slice_config = None
        else:
            slice_config = self._slice_config(job_name, raw_execution)
        if (
            materialized == "incremental"
            and strategy == "replay_slices"
            and slice_config is None
        ):
            raise ExecutionConfigError(
                f"[{job_name}] incremental + replay_slices requires "
                "model execution.slice or warehouse execution.default_slice"
            )

        if slice_config is not None:
            self._validate_slice_column(job_name, Path(sql_path), slice_config)

        companion_path = self._companion_path(Path(sql_path), job_name)
        if strategy == "companion" and companion_path is None:
            raise ExecutionConfigError(
                f"[{job_name}] execution.full_refresh_strategy: companion "
                f"requires tasks/full_refresh/{job_name}_full_refresh.sql"
            )

        return TaskSpec(
            job_name=job_name,
            sql_path=Path(sql_path),
            materialized=materialized,
            full_refresh_strategy=strategy,
            slice_param=slice_config.param if slice_config else None,
            slice_column=slice_config.column if slice_config else None,
            slice_period=slice_config.period if slice_config else None,
            companion_path=companion_path,
            historical_replay_supported=bool(
                raw_execution.get("historical_replay_supported", True)
            ),
        )

    def plan_regular_run(
        self,
        spec: TaskSpec,
        slice_values: list[str | None] | None = None,
    ) -> list[TaskInvocation]:
        if spec.materialized == "full":
            return [
                TaskInvocation(
                    job_name=spec.job_name,
                    sql_path=spec.sql_path,
                    params={},
                    full_refresh=True,
                    strategy=spec.full_refresh_strategy,
                )
            ]

        values = list(slice_values or [None])
        if spec.slice_param:
            normalized = self._normalize_slice_values(
                values, spec.slice_period
            )
            self._validate_historical_replay(spec, normalized)
            if not normalized:
                return [
                    TaskInvocation(
                        job_name=spec.job_name,
                        sql_path=spec.sql_path,
                        params={},
                        full_refresh=False,
                        strategy=spec.full_refresh_strategy,
                    )
                ]
            return [
                TaskInvocation(
                    job_name=spec.job_name,
                    sql_path=spec.sql_path,
                    params={spec.slice_param: value},
                    full_refresh=False,
                    strategy=spec.full_refresh_strategy,
                )
                for value in normalized
            ]

        return [
            TaskInvocation(
                job_name=spec.job_name,
                sql_path=spec.sql_path,
                params={},
                full_refresh=False,
                strategy=spec.full_refresh_strategy,
            )
        ]

    def _validate_historical_replay(
        self,
        spec: TaskSpec,
        values: list[str],
    ) -> None:
        if spec.historical_replay_supported:
            return
        current_date = date.today().isoformat()
        unsupported = [value for value in values if value != current_date]
        if unsupported:
            raise ExecutionConfigError(
                f"[{spec.job_name}] current-state capture does not support "
                f"historical replay; expected {current_date}, got "
                f"{', '.join(unsupported)}"
            )

    def plan_full_refresh(
        self,
        spec: TaskSpec,
        slice_values: list[str],
    ) -> list[TaskInvocation]:
        strategy = spec.full_refresh_strategy
        if strategy == "replay_slices":
            normalized = self._normalize_slice_values(
                list(slice_values),
                spec.slice_period,
            )
            self._validate_historical_replay(spec, normalized)
            return [
                TaskInvocation(
                    job_name=spec.job_name,
                    sql_path=spec.sql_path,
                    params={spec.slice_param: value}
                    if spec.slice_param
                    else {},
                    full_refresh=False,
                    strategy=strategy,
                )
                for value in normalized
            ]

        sql_path = (
            spec.companion_path if strategy == "companion" else spec.sql_path
        )
        params = (
            self._full_refresh_window_params(slice_values)
            if strategy == "companion"
            else {}
        )
        return [
            TaskInvocation(
                job_name=spec.job_name,
                sql_path=sql_path or spec.sql_path,
                params=params,
                full_refresh=True,
                strategy=strategy,
            )
        ]

    def plan_shadow_job(
        self,
        job: dict,
        *,
        project_root: Path | None = None,
        full_refresh: bool = False,
    ) -> list[TaskInvocation]:
        job_name = str(job.get("job") or "").strip()
        sql_path = self._job_sql_path(job, project_root=project_root)
        spec = self.task_spec(job_name, sql_path)
        if full_refresh:
            return self.plan_full_refresh(
                spec,
                [str(value) for value in job.get("execution_values") or []],
            )
        return self.plan_regular_run(spec, self._job_execution_values(job))

    def _project_config(self) -> dict:
        raw = config.core.PROJECT_CONFIG.get(self.project)
        if raw:
            return dict(raw)

        warehouse_path = (
            self.project_root / "warehouses" / self.project / "warehouse.yaml"
        )
        if warehouse_path.exists():
            return config.core.load_warehouse_config(
                warehouse_path,
                project_root=self.project_root,
            )
        return {"dir": f"warehouses/{self.project}"}

    def _project_dir(self) -> Path:
        raw_dir = str(
            self.project_config.get("dir") or f"warehouses/{self.project}"
        )
        path = Path(raw_dir)
        if path.is_absolute():
            return path
        return self.project_root / path

    def _warehouse_execution_config(self) -> dict:
        raw = self.project_config.get("execution")
        if isinstance(raw, dict):
            return dict(raw)

        warehouse_path = self.project_dir / "warehouse.yaml"
        if not warehouse_path.exists():
            return {}
        data = (
            yaml.safe_load(
                warehouse_path.read_text(encoding=config.TEXT_ENCODING)
            )
            or {}
        )
        execution = data.get("execution") or {}
        return dict(execution) if isinstance(execution, dict) else {}

    def _load_model_metadata(self) -> dict[str, dict]:
        metadata = {}
        model_roots = [
            self.project_dir / "ods" / "models",
            self.project_dir / "mid" / "models",
            self.project_dir / "ads" / "models",
        ]
        for model_root in model_roots:
            if not model_root.exists():
                continue
            for model_path in sorted(model_root.rglob("*.yaml")):
                raw = (
                    yaml.safe_load(
                        model_path.read_text(encoding=config.TEXT_ENCODING)
                    )
                    or {}
                )
                if not isinstance(raw, dict):
                    continue
                name = raw.get("name") or model_path.stem
                raw = dict(raw)
                raw["name"] = name
                metadata[str(name)] = raw
        return metadata

    def _slice_config(
        self, job_name: str, raw_execution: dict
    ) -> SliceConfig | None:
        model_slice = slice_config_from_mapping(
            job_name,
            raw_execution.get("slice"),
            label="execution.slice",
        )
        if model_slice is not None:
            return model_slice
        return slice_config_from_mapping(
            job_name,
            self.warehouse_execution.get("default_slice"),
            label="execution.default_slice",
        )

    def _validate_slice_column(
        self,
        job_name: str,
        sql_path: Path,
        slice_config: SliceConfig,
    ) -> None:
        ddl_path = self._ddl_path(sql_path, job_name)
        if not ddl_path.exists():
            return
        ddl_text = ddl_path.read_text(encoding=config.TEXT_ENCODING)
        if not _contains_identifier(ddl_text, slice_config.column):
            raise ExecutionConfigError(
                f"[{job_name}] execution.slice.column "
                f"'{slice_config.column}' does not exist in DDL: {ddl_path}"
            )

    def _ddl_path(self, sql_path: Path, job_name: str) -> Path:
        task_dir = sql_path.parent
        if task_dir.name == "full_refresh":
            task_dir = task_dir.parent
        return task_dir.parent / "ddl" / f"{job_name}.sql"

    def _companion_path(self, sql_path: Path, job_name: str) -> Path | None:
        task_dir = sql_path.parent
        if task_dir.name == "full_refresh":
            task_dir = task_dir.parent
        companion = task_dir / "full_refresh" / f"{job_name}_full_refresh.sql"
        return companion if companion.exists() else None

    def _job_sql_path(
        self,
        job: dict,
        *,
        project_root: Path | None,
    ) -> Path:
        root = Path(project_root or self.project_root)
        raw_file = str(job.get("file") or "").strip()
        if raw_file:
            path = Path(raw_file)
            return path if path.is_absolute() else root / path
        candidate = config.task_path_for_job(
            self.project, str(job.get("job") or "")
        )
        if candidate is None:
            return root / f"{job.get('job')}.sql"
        return candidate

    def _job_execution_values(
        self,
        job: dict,
    ) -> list[str | None]:
        values = job.get("execution_values")
        if values:
            return [str(value) for value in values]
        return [None]

    def _normalize_slice_values(
        self,
        values: list[str | None],
        period: str | None,
    ) -> list[str]:
        normalized = []
        seen = set()
        for value in values:
            if value is None:
                continue
            item = _normalize_slice_value(str(value), period)
            if item in seen:
                continue
            seen.add(item)
            normalized.append(item)
        return normalized

    def _full_refresh_window_params(
        self,
        slice_values: list[str],
    ) -> dict[str, str]:
        raw_window = self.warehouse_execution.get("full_refresh_window")
        if not isinstance(raw_window, dict) or not slice_values:
            return {}
        start_param = str(raw_window.get("start_param") or "").strip()
        end_param = str(raw_window.get("end_param") or "").strip()
        if not start_param or not end_param:
            raise ExecutionConfigError(
                "warehouse execution.full_refresh_window requires "
                "start_param and end_param"
            )
        normalized = self._normalize_slice_values(
            [str(value) for value in slice_values],
            "D",
        )
        if not normalized:
            return {}
        ordered = sorted(normalized)
        parsed = [
            datetime.strptime(value, "%Y-%m-%d").date() for value in ordered
        ]
        if any(
            current - previous != timedelta(days=1)
            for previous, current in zip(parsed, parsed[1:])
        ):
            raise ExecutionConfigError(
                "full refresh window requires contiguous daily slice values"
            )
        return {
            start_param: ordered[0],
            end_param: ordered[-1],
        }


def _normalize_slice_value(value: str, period: str | None) -> str:
    normalized_period = str(period or "D").upper()
    if normalized_period == "D":
        return value
    if normalized_period == "H":
        return value

    date_value = datetime.strptime(value[:10], "%Y-%m-%d").date()
    if normalized_period == "M":
        return date_value.replace(day=1).isoformat()
    if normalized_period == "W":
        week_start = date_value - timedelta(days=date_value.weekday())
        return week_start.isoformat()
    return value


def _contains_identifier(sql_text: str, identifier: str) -> bool:
    wanted = identifier.casefold()
    for match in re.finditer(
        r"`([^`]+)`|\"([^\"]+)\"|\b([A-Za-z_][A-Za-z0-9_]*)\b",
        sql_text,
    ):
        token = next(group for group in match.groups() if group)
        if token.casefold() == wanted:
            return True
    return False
