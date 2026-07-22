"""Shared task execution planner for direct and shadow runs."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import yaml

import dw_refactor_agent.config as config
from dw_refactor_agent.config.assets import ProjectTaskAsset
from dw_refactor_agent.execution.invocation import TaskInvocation
from dw_refactor_agent.execution.model_config import (
    ExecutionConfigError,
    SliceConfig,
    execution_config_for_model,
    normalize_materialized,
    normalize_strategy,
    slice_config_from_mapping,
)
from dw_refactor_agent.lineage.identifiers import identifier_match_key
from dw_refactor_agent.sql.task_execution import (
    load_execution_task_asset,
    render_task_execution_sql,
)
from dw_refactor_agent.sql.task_template import TaskTemplateError


@dataclass(frozen=True)
class ResolvedExecutionContract:
    """Validated join of model scheduling and task variable metadata."""

    task_assets: tuple[ProjectTaskAsset, ...]
    slice_param: str | None

    def asset_for_path(self, path: Path) -> ProjectTaskAsset | None:
        target = Path(path).resolve()
        for asset in self.task_assets:
            if asset.sql_path.resolve() == target:
                return asset
        return None


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
    execution_contract: ResolvedExecutionContract | None = None


class ExecutionPlanner:
    """Create task invocations from warehouse/model execution config."""

    def __init__(
        self,
        project: str,
        project_root: Path | None = None,
        *,
        db_env: str = "prod",
    ):
        self.project = project
        self.db_env = str(db_env)
        self._has_explicit_project_root = project_root is not None
        self.project_root = Path(project_root or config.core.PROJECT_ROOT)
        self.project_config = self._project_config()
        self.project_dir = self._project_dir()
        self.warehouse_execution = self._warehouse_execution_config()
        self.model_metadata = self._load_model_metadata()
        self._task_asset_cache: dict[Path, ProjectTaskAsset] = {}

    def task_spec(
        self,
        job_name: str,
        sql_path: Path,
        *,
        model_name: str | None = None,
    ) -> TaskSpec:
        execution_model_name = str(model_name or job_name).strip()
        raw_model = self.model_metadata.get(
            identifier_match_key(execution_model_name), {}
        )
        raw_execution = execution_config_for_model(
            execution_model_name,
            raw_model,
        )

        materialized = normalize_materialized(
            execution_model_name,
            raw_execution.get("materialized", "incremental"),
        )
        strategy = normalize_strategy(
            execution_model_name,
            materialized,
            raw_execution.get("full_refresh_strategy"),
        )
        # Full models do not consume the warehouse default slice.  Reject an
        # explicit model slice instead of silently accepting contradictory
        # execution metadata.
        if materialized == "full":
            explicit_slice = slice_config_from_mapping(
                execution_model_name,
                raw_execution.get("slice"),
                label="execution.slice",
            )
            if explicit_slice is not None:
                raise ExecutionConfigError(
                    f"[{execution_model_name}] full models cannot define "
                    "execution.slice"
                )
            slice_config = None
        else:
            slice_config = self._slice_config(
                execution_model_name,
                raw_execution,
            )
        if (
            materialized == "incremental"
            and strategy == "replay_slices"
            and slice_config is None
        ):
            raise ExecutionConfigError(
                f"[{execution_model_name}] incremental + replay_slices "
                "requires "
                "model execution.slice or warehouse execution.default_slice"
            )

        if slice_config is not None:
            self._validate_slice_column(
                execution_model_name,
                Path(sql_path),
                slice_config,
            )

        companion_path = self._companion_path(Path(sql_path), job_name)
        if strategy == "companion" and companion_path is None:
            raise ExecutionConfigError(
                f"[{job_name}] execution.full_refresh_strategy: companion "
                f"requires tasks/full_refresh/{job_name}_full_refresh.sql"
            )

        try:
            task_assets = [self._task_asset(Path(sql_path))]
            self._validate_task_slice_contract(
                execution_model_name,
                task_assets[0],
                expected_slice_param=(
                    slice_config.param if slice_config else None
                ),
                allowed_partition_params=(
                    {slice_config.param} if slice_config else set()
                ),
            )
            if strategy == "companion" and companion_path is not None:
                companion_asset = self._task_asset(companion_path)
                self._validate_task_slice_contract(
                    execution_model_name,
                    companion_asset,
                    expected_slice_param=None,
                    allowed_partition_params=set(
                        self._full_refresh_window_param_names()
                    ),
                )
                task_assets.append(companion_asset)
        except TaskTemplateError as exc:
            raise ExecutionConfigError(
                f"[{job_name}] task template is invalid: {exc}"
            ) from exc

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
            execution_contract=ResolvedExecutionContract(
                task_assets=tuple(task_assets),
                slice_param=slice_config.param if slice_config else None,
            ),
        )

    def _task_asset(self, sql_path: Path) -> ProjectTaskAsset:
        key = Path(sql_path).resolve()
        if key not in self._task_asset_cache:
            self._task_asset_cache[key] = load_execution_task_asset(
                self.project,
                Path(sql_path),
            )
        return self._task_asset_cache[key]

    def _validate_task_slice_contract(
        self,
        model_name: str,
        asset: ProjectTaskAsset,
        *,
        expected_slice_param: str | None,
        allowed_partition_params: set[str],
    ) -> None:
        if not asset.is_template:
            return
        usage = asset.template_definition.contract.usage
        usage_params = {item.parameter for item in usage.slices}
        expected = {expected_slice_param} if expected_slice_param else set()
        if usage_params != expected:
            raise ExecutionConfigError(
                f"[{model_name}] task usage.slices parameters "
                f"{sorted(usage_params)!r} must match execution.slice.param "
                f"{sorted(expected)!r}"
            )
        partition_params = {item.parameter for item in usage.partitions}
        if not partition_params.issubset(allowed_partition_params):
            raise ExecutionConfigError(
                f"[{model_name}] task usage.partitions parameters "
                f"{sorted(partition_params)!r} must be provided by "
                "the invocation parameters "
                f"{sorted(allowed_partition_params)!r}"
            )
        contract = asset.template_definition.contract
        parameters = contract.parameters_by_name

        def startup_roots(prop: str) -> set[str]:
            pending = [prop]
            seen = set()
            roots = set()
            while pending:
                current = pending.pop()
                if current in seen:
                    continue
                seen.add(current)
                definition = parameters[current]
                dependencies = definition.dependencies()
                if dependencies:
                    pending.extend(dependencies)
                    continue
                roots.add(current)
            return roots

        startup_by_prop = {item.prop: item for item in contract.startup_params}
        for mapping in usage.slices + usage.partitions:
            valid_parameters = set()
            for root in startup_roots(mapping.prop):
                startup = startup_by_prop.get(root)
                if startup is None:
                    continue
                valid_parameters.add(startup.prop)
                prefix = "invocation."
                if startup.source and startup.source.startswith(prefix):
                    valid_parameters.add(startup.source[len(prefix) :])
            if mapping.parameter not in valid_parameters:
                raise ExecutionConfigError(
                    f"[{model_name}] task usage.{mapping.kind}s prop "
                    f"{mapping.prop!r} is not derived from startup "
                    f"parameter {mapping.parameter!r}"
                )

    def _invocation(
        self,
        spec: TaskSpec,
        *,
        sql_path: Path,
        params: dict[str, str],
        full_refresh: bool,
        strategy: str,
    ) -> TaskInvocation:
        contract = spec.execution_contract
        asset = contract.asset_for_path(sql_path) if contract else None
        try:
            asset = asset or self._task_asset(sql_path)
            rendered = render_task_execution_sql(
                asset,
                session_params=params,
                project_config=self.project_config,
                environment=self.db_env,
            )
        except TaskTemplateError as exc:
            raise ExecutionConfigError(
                f"[{spec.job_name}] task render failed: {exc}"
            ) from exc
        public_summary = {}
        if rendered.is_template:
            public_summary = dict(rendered.public_summary)
            public_summary["session_params"] = dict(
                rendered.public_session_params
            )
        return TaskInvocation(
            job_name=spec.job_name,
            sql_path=sql_path,
            params=params,
            full_refresh=full_refresh,
            strategy=strategy,
            render_inputs=rendered.render_inputs,
            resolved_sql=rendered.sql,
            public_summary=public_summary,
        )

    def plan_regular_run(
        self,
        spec: TaskSpec,
        slice_values: list[str | None] | None = None,
    ) -> list[TaskInvocation]:
        if spec.materialized == "full":
            return [
                self._invocation(
                    spec,
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
                    self._invocation(
                        spec,
                        sql_path=spec.sql_path,
                        params={},
                        full_refresh=False,
                        strategy=spec.full_refresh_strategy,
                    )
                ]
            return [
                self._invocation(
                    spec,
                    sql_path=spec.sql_path,
                    params={spec.slice_param: value},
                    full_refresh=False,
                    strategy=spec.full_refresh_strategy,
                )
                for value in normalized
            ]

        return [
            self._invocation(
                spec,
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
                self._invocation(
                    spec,
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
            self._invocation(
                spec,
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
        model_name = str(job.get("target") or job_name).strip()
        sql_path = self._job_sql_path(job, project_root=project_root)
        spec = self.task_spec(
            job_name,
            sql_path,
            model_name=model_name,
        )
        if full_refresh:
            return self.plan_full_refresh(
                spec,
                [str(value) for value in job.get("execution_values") or []],
            )
        return self.plan_regular_run(spec, self._job_execution_values(job))

    def _project_config(self) -> dict:
        if self._has_explicit_project_root:
            rooted_config = config.core.load_project_config(self.project_root)
            raw = rooted_config.get(self.project)
            if raw:
                return dict(raw)
            warehouse_path = (
                self.project_root
                / "warehouses"
                / self.project
                / "warehouse.yaml"
            )
            if warehouse_path.exists():
                return config.core.load_warehouse_config(
                    warehouse_path,
                    project_root=self.project_root,
                )
            return {"dir": f"warehouses/{self.project}"}
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
                name_key = identifier_match_key(name)
                if name_key in metadata:
                    raise ExecutionConfigError(
                        "duplicate model metadata names under "
                        f"case-insensitive matching: {name!r}"
                    )
                metadata[name_key] = raw
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
        ddl_dir = task_dir.parent / "ddl"
        candidate = ddl_dir / f"{job_name}.sql"
        if not ddl_dir.exists():
            return candidate
        job_key = identifier_match_key(job_name)
        matches = [
            path
            for path in sorted(ddl_dir.glob("*.sql"))
            if identifier_match_key(path.stem) == job_key
        ]
        if len(matches) > 1:
            raise ExecutionConfigError(
                "multiple DDL files match execution model "
                f"{job_name!r} case-insensitively: "
                f"{[str(path) for path in matches]!r}"
            )
        return matches[0] if matches else candidate

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
        parameter_names = self._full_refresh_window_param_names()
        raw_window = self.warehouse_execution.get("full_refresh_window")
        if not isinstance(raw_window, dict) or not slice_values:
            return {}
        start_param, end_param = parameter_names
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

    def _full_refresh_window_param_names(self) -> tuple[str, ...]:
        raw_window = self.warehouse_execution.get("full_refresh_window")
        if not isinstance(raw_window, dict):
            return ()
        start_param = str(raw_window.get("start_param") or "").strip()
        end_param = str(raw_window.get("end_param") or "").strip()
        if not start_param or not end_param:
            raise ExecutionConfigError(
                "warehouse execution.full_refresh_window requires "
                "start_param and end_param"
            )
        if start_param == end_param:
            raise ExecutionConfigError(
                "warehouse execution.full_refresh_window start_param and "
                "end_param must be different"
            )
        return start_param, end_param


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
