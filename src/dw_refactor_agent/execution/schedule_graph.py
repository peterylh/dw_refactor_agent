"""Trusted project schedule DAG contract and graph operations."""

from __future__ import annotations

import json
import os
import tempfile
from collections import deque
from contextlib import suppress
from pathlib import Path
from typing import Collection

import dw_refactor_agent.config as config
from dw_refactor_agent.lineage.identifiers import identifier_match_key

SCHEDULE_FORMAT_VERSION = 1


class ScheduleContractError(ValueError):
    """Raised when a trusted schedule DAG violates its contract."""


def configured_schedule_path(
    project: str,
    *,
    root: Path | None = None,
    project_config: dict | None = None,
) -> Path:
    """Resolve ``execution.schedule`` relative to the warehouse directory."""
    if project_config is None:
        project_config = config.PROJECT_CONFIG.get(project)
    if project_config is None:
        raise ScheduleContractError(f"unknown project: {project!r}")
    execution = project_config.get("execution") or {}
    raw_path = execution.get("schedule")
    if not isinstance(raw_path, str) or not raw_path.strip():
        raise ScheduleContractError(
            f"[{project}] execution.schedule must be a non-empty path"
        )
    path = Path(raw_path)
    if path.is_absolute():
        raise ScheduleContractError(
            f"[{project}] execution.schedule must be relative to the "
            "warehouse directory"
        )
    project_root = Path(root) if root is not None else config.PROJECT_ROOT
    project_dir = project_root / project_config["dir"]
    resolved_project_dir = project_dir.resolve()
    resolved = (project_dir / path).resolve()
    try:
        resolved.relative_to(resolved_project_dir)
    except ValueError:
        raise ScheduleContractError(
            f"[{project}] execution.schedule escapes the warehouse "
            f"directory: {raw_path}"
        ) from None
    return resolved


class ScheduleGraph:
    """A normalized, case-insensitive trusted Job dependency DAG.

    ``dependencies[downstream]`` contains the downstream Job's direct
    upstream Jobs. The persisted representation omits empty dependency lists.
    """

    def __init__(
        self,
        project: str,
        jobs: Collection[str],
        dependencies: dict[str, Collection[str]] | None = None,
    ) -> None:
        self.project = self._non_empty_string(project, "project")
        self._jobs_by_key = {}
        for raw_job in jobs:
            job = self._non_empty_string(raw_job, "jobs[]")
            key = identifier_match_key(job)
            if key in self._jobs_by_key:
                raise ScheduleContractError(
                    f"duplicate schedule Job (case-insensitive): {job!r}"
                )
            self._jobs_by_key[key] = job
        self._jobs = sorted(
            self._jobs_by_key.values(), key=identifier_match_key
        )

        self._upstreams = {job: set() for job in self._jobs}
        for raw_downstream, raw_upstreams in (dependencies or {}).items():
            downstream = self.resolve_job(raw_downstream)
            if downstream is None:
                raise ScheduleContractError(
                    "schedule dependency references unknown downstream Job: "
                    f"{raw_downstream!r}"
                )
            if not isinstance(raw_upstreams, (list, tuple, set, frozenset)):
                raise ScheduleContractError(
                    f"dependencies[{raw_downstream!r}] must be a list"
                )
            seen = set()
            for raw_upstream in raw_upstreams:
                upstream = self.resolve_job(raw_upstream)
                if upstream is None:
                    raise ScheduleContractError(
                        "schedule dependency references unknown upstream Job: "
                        f"{raw_upstream!r}"
                    )
                upstream_key = identifier_match_key(upstream)
                if upstream_key in seen:
                    raise ScheduleContractError(
                        f"dependencies[{downstream!r}] contains duplicate "
                        f"upstream Job: {upstream!r}"
                    )
                seen.add(upstream_key)
                if upstream_key == identifier_match_key(downstream):
                    raise ScheduleContractError(
                        f"schedule dependency cannot be a self-edge: {upstream}"
                    )
                self._upstreams[downstream].add(upstream)

        self._downstreams = {job: set() for job in self._jobs}
        for downstream, upstreams in self._upstreams.items():
            for upstream in upstreams:
                self._downstreams[upstream].add(downstream)
        self.topological_sort(set(self._jobs))

    @staticmethod
    def _non_empty_string(value, field: str) -> str:
        if not isinstance(value, str) or not value.strip():
            raise ScheduleContractError(
                f"schedule {field} must be a non-empty string"
            )
        return value.strip()

    @property
    def jobs(self) -> list[str]:
        return list(self._jobs)

    @property
    def dependencies(self) -> dict[str, list[str]]:
        return {
            job: sorted(self._upstreams[job], key=identifier_match_key)
            for job in self._jobs
            if self._upstreams[job]
        }

    @property
    def edges(self) -> set[tuple[str, str]]:
        return {
            (upstream, downstream)
            for downstream, upstreams in self._upstreams.items()
            for upstream in upstreams
        }

    def resolve_job(self, job: str) -> str | None:
        return self._jobs_by_key.get(identifier_match_key(job))

    def direct_upstreams(self, job: str) -> set[str]:
        resolved = self.resolve_job(job)
        return set(self._upstreams.get(resolved, set()))

    def direct_downstreams(self, job: str) -> set[str]:
        resolved = self.resolve_job(job)
        return set(self._downstreams.get(resolved, set()))

    def bfs_downstream(self, seeds: Collection[str]) -> set[str]:
        resolved_seeds = {
            resolved
            for seed in seeds
            for resolved in [self.resolve_job(seed)]
            if resolved is not None
        }
        visited = set(resolved_seeds)
        queue = deque(sorted(resolved_seeds, key=identifier_match_key))
        while queue:
            job = queue.popleft()
            for downstream in sorted(
                self._downstreams[job], key=identifier_match_key
            ):
                if downstream in visited:
                    continue
                visited.add(downstream)
                queue.append(downstream)
        return visited - resolved_seeds

    def bfs_upstream(self, seeds: Collection[str]) -> set[str]:
        resolved_seeds = {
            resolved
            for seed in seeds
            for resolved in [self.resolve_job(seed)]
            if resolved is not None
        }
        visited = set(resolved_seeds)
        queue = deque(sorted(resolved_seeds, key=identifier_match_key))
        while queue:
            job = queue.popleft()
            for upstream in sorted(
                self._upstreams[job], key=identifier_match_key
            ):
                if upstream in visited:
                    continue
                visited.add(upstream)
                queue.append(upstream)
        return visited - resolved_seeds

    def has_path(self, upstream: str, downstream: str) -> bool:
        resolved_upstream = self.resolve_job(upstream)
        resolved_downstream = self.resolve_job(downstream)
        if resolved_upstream is None or resolved_downstream is None:
            return False
        if resolved_upstream == resolved_downstream:
            return True
        return resolved_downstream in self.bfs_downstream({resolved_upstream})

    def compute_in_degree(
        self, jobs: Collection[str]
    ) -> tuple[dict[str, int], dict[str, list[str]]]:
        selected_by_key = {}
        for raw_job in jobs:
            resolved = self.resolve_job(raw_job)
            if resolved is None:
                raise ScheduleContractError(
                    f"selected Job is absent from schedule DAG: {raw_job!r}"
                )
            selected_by_key[identifier_match_key(resolved)] = resolved
        selected = set(selected_by_key.values())
        in_degree = dict.fromkeys(selected, 0)
        adjacency = {job: [] for job in selected}
        for upstream in selected:
            for downstream in self._downstreams[upstream]:
                if downstream not in selected:
                    continue
                adjacency[upstream].append(downstream)
                in_degree[downstream] += 1
        for upstream in adjacency:
            adjacency[upstream].sort(key=identifier_match_key)
        return in_degree, adjacency

    def selected_dependencies(
        self, jobs: Collection[str]
    ) -> dict[str, list[str]]:
        selected = {self.resolve_job(job) for job in jobs}
        if None in selected:
            missing = sorted(
                job for job in jobs if self.resolve_job(job) is None
            )
            raise ScheduleContractError(
                f"selected Jobs are absent from schedule DAG: {missing!r}"
            )
        return {
            job: sorted(
                self._upstreams[job].intersection(selected),
                key=identifier_match_key,
            )
            for job in sorted(selected, key=identifier_match_key)
        }

    def omitted_upstreams(self, jobs: Collection[str]) -> dict[str, list[str]]:
        selected = {
            resolved
            for job in jobs
            for resolved in [self.resolve_job(job)]
            if resolved is not None
        }
        return {
            job: sorted(
                self._upstreams[job] - selected, key=identifier_match_key
            )
            for job in sorted(selected, key=identifier_match_key)
            if self._upstreams[job] - selected
        }

    def topological_sort(self, jobs: Collection[str]) -> list[str]:
        in_degree, adjacency = self.compute_in_degree(jobs)
        ready = sorted(
            (job for job, degree in in_degree.items() if degree == 0),
            key=identifier_match_key,
        )
        result = []
        while ready:
            job = ready.pop(0)
            result.append(job)
            for downstream in adjacency[job]:
                in_degree[downstream] -= 1
                if in_degree[downstream] == 0:
                    ready.append(downstream)
            ready.sort(key=identifier_match_key)
        if len(result) != len(in_degree):
            cycle_jobs = sorted(
                set(in_degree) - set(result), key=identifier_match_key
            )
            raise ScheduleContractError(
                f"schedule DAG contains a cycle among Jobs: {cycle_jobs!r}"
            )
        return result

    def to_dict(self) -> dict:
        return {
            "format_version": SCHEDULE_FORMAT_VERSION,
            "project": self.project,
            "jobs": self.jobs,
            "dependencies": self.dependencies,
        }

    @classmethod
    def from_dict(
        cls,
        data: dict,
        *,
        expected_project: str | None = None,
    ) -> "ScheduleGraph":
        if not isinstance(data, dict):
            raise ScheduleContractError("schedule DAG must be a JSON object")
        allowed = {"format_version", "project", "jobs", "dependencies"}
        unexpected = sorted(set(data) - allowed)
        if unexpected:
            raise ScheduleContractError(
                f"schedule DAG contains unsupported fields: {unexpected!r}"
            )
        if data.get("format_version") != SCHEDULE_FORMAT_VERSION:
            raise ScheduleContractError(
                "schedule DAG format_version must be integer 1"
            )
        project = cls._non_empty_string(data.get("project"), "project")
        if expected_project is not None and project != expected_project:
            raise ScheduleContractError(
                f"schedule DAG project mismatch: expected {expected_project!r}, "
                f"got {project!r}"
            )
        jobs = data.get("jobs")
        if not isinstance(jobs, list):
            raise ScheduleContractError("schedule jobs must be a list")
        dependencies = data.get("dependencies", {})
        if not isinstance(dependencies, dict):
            raise ScheduleContractError(
                "schedule dependencies must be a mapping"
            )
        return cls(project, jobs, dependencies)

    @classmethod
    def load(
        cls,
        path: Path,
        *,
        expected_project: str | None = None,
    ) -> "ScheduleGraph":
        path = Path(path)
        try:
            data = json.loads(path.read_text(encoding=config.TEXT_ENCODING))
        except FileNotFoundError:
            raise ScheduleContractError(
                f"trusted schedule DAG does not exist: {path}"
            ) from None
        except (OSError, json.JSONDecodeError) as exc:
            raise ScheduleContractError(
                f"cannot read trusted schedule DAG {path}: {exc}"
            ) from exc
        return cls.from_dict(data, expected_project=expected_project)

    @classmethod
    def load_for_project(
        cls,
        project: str,
        *,
        root: Path | None = None,
        project_config: dict | None = None,
    ) -> "ScheduleGraph":
        return cls.load(
            configured_schedule_path(
                project, root=root, project_config=project_config
            ),
            expected_project=project,
        )

    def save(self, path: Path) -> None:
        path = Path(path)
        path.parent.mkdir(parents=True, exist_ok=True)
        payload = (
            json.dumps(self.to_dict(), ensure_ascii=False, indent=2).encode(
                config.TEXT_ENCODING
            )
            + b"\n"
        )
        descriptor, temporary_name = tempfile.mkstemp(
            prefix=f".{path.name}.", suffix=".tmp", dir=str(path.parent)
        )
        try:
            with os.fdopen(descriptor, "wb") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(temporary_name, path)
        except Exception:
            with suppress(FileNotFoundError):
                os.unlink(temporary_name)
            raise
