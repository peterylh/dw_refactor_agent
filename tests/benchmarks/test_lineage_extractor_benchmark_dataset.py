import json
import os
import subprocess
import sys

from benchmarks.lineage_extractor.dataset import (
    PROFILES,
    generate_dataset,
)
from benchmarks.lineage_extractor.run import run_benchmark
from lineage.lineage_extractor import (
    build_schema_from_texts,
    extract_lineage_from_task_files,
)


def test_profiles_match_advertised_counts():
    assert set(PROFILES) == {"small", "medium", "large"}

    for profile in PROFILES.values():
        assert profile.table_count == (
            profile.ods_tables
            + profile.dwd_tables
            + profile.dws_tables
            + profile.ads_tables
        )
        assert profile.task_count == (
            profile.dwd_tables + profile.dws_tables + profile.ads_tables
        )


def test_small_dataset_generation_is_structurally_consistent(tmp_path):
    dataset = generate_dataset("small", tmp_path)

    assert dataset.profile.name == "small"
    assert dataset.table_count == 50
    assert dataset.task_count == 40
    assert len(dataset.ddl_files) == 50
    assert len(dataset.task_files) == 40
    assert 800 <= dataset.column_count <= 1200
    assert dataset.expected_min_edges >= dataset.task_count

    names = [path.name for path in dataset.task_files[:3]]
    assert names == [
        "dwd_fact_0000.sql",
        "dwd_fact_0001.sql",
        "dwd_fact_0002.sql",
    ]


def test_generated_task_can_build_lineage(tmp_path):
    dataset = generate_dataset("small", tmp_path)
    schema = build_schema_from_texts(
        [path.read_text(encoding="utf-8") for path in dataset.ddl_files],
        default_catalog=dataset.catalog,
        default_db=dataset.database,
    )

    result = extract_lineage_from_task_files(
        [dataset.task_files[0]],
        dataset.tasks_dir,
        schema,
        parallel=1,
        cache_project=dataset.project_name,
    )

    assert result["errors"] == []
    assert len(result["lineage"]) >= 8


def test_high_complexity_dataset_generates_transient_table_tasks(tmp_path):
    dataset = generate_dataset("small", tmp_path, complexity="high")
    task_texts = [
        path.read_text(encoding="utf-8") for path in dataset.task_files
    ]

    assert any("CREATE TEMPORARY TABLE" in text for text in task_texts)

    schema = build_schema_from_texts(
        [path.read_text(encoding="utf-8") for path in dataset.ddl_files],
        default_catalog=dataset.catalog,
        default_db=dataset.database,
    )
    task_file = next(
        path
        for path in dataset.task_files
        if "CREATE TEMPORARY TABLE" in path.read_text(encoding="utf-8")
    )
    result = extract_lineage_from_task_files(
        [task_file],
        dataset.tasks_dir,
        schema,
        parallel=1,
        cache_project=dataset.project_name,
    )

    assert result["errors"] == []
    assert result["transient_tables"]
    assert len(result["lineage"]) >= 8


def test_stress_complexity_dataset_generates_transient_table_chains(tmp_path):
    dataset = generate_dataset("small", tmp_path, complexity="stress")
    task_texts = [
        path.read_text(encoding="utf-8") for path in dataset.task_files
    ]

    assert any(
        text.count("CREATE TEMPORARY TABLE") >= 2 for text in task_texts
    )

    schema = build_schema_from_texts(
        [path.read_text(encoding="utf-8") for path in dataset.ddl_files],
        default_catalog=dataset.catalog,
        default_db=dataset.database,
    )
    task_file = next(
        path
        for path in dataset.task_files
        if path.read_text(encoding="utf-8").count("CREATE TEMPORARY TABLE")
        >= 2
    )
    result = extract_lineage_from_task_files(
        [task_file],
        dataset.tasks_dir,
        schema,
        parallel=1,
        cache_project=dataset.project_name,
    )

    assert result["errors"] == []
    assert len(result["transient_tables"]) >= 2
    assert len(result["lineage"]) >= 8


def test_run_benchmark_writes_json_report(tmp_path):
    report_path = tmp_path / "report.json"

    report = run_benchmark(
        size="small",
        complexity="high",
        parallel=1,
        repeat=1,
        output_path=report_path,
        asset_dir=tmp_path / "assets",
        keep_assets=True,
    )

    assert report["benchmark"] == "lineage_extractor"
    assert report["size"] == "small"
    assert report["complexity"] == "high"
    assert report["dataset"]["tables"] == 50
    assert report["dataset"]["tasks"] == 40
    assert len(report["results"]) == 1
    assert report["results"][0]["warm_cache_hits"] == 40
    assert report["results"][0]["errors"] == 0
    assert report_path.exists()
    assert json.loads(report_path.read_text(encoding="utf-8")) == report


def test_run_benchmark_writes_cprofile_report(tmp_path):
    profile_path = tmp_path / "profile.json"

    report = run_benchmark(
        size="small",
        complexity="normal",
        parallel=1,
        repeat=1,
        asset_dir=tmp_path / "assets",
        keep_assets=True,
        profile="cprofile",
        profile_output_path=profile_path,
        profile_limit=5,
    )

    profile = report["profile"]
    assert profile["mode"] == "cprofile"
    assert profile["phase_percentages"]["cold_extraction"] > 0
    assert profile["cache_impact"]["warm_cache_hits"] == 40
    assert len(profile["top_functions"]) <= 5
    assert profile["top_functions"][0]["cumulative_seconds"] > 0
    assert profile_path.exists()
    assert json.loads(profile_path.read_text(encoding="utf-8")) == profile


def test_runner_script_help_works_without_pythonpath():
    env = dict(os.environ)
    env["PYTHONPATH"] = ""

    result = subprocess.run(
        [
            sys.executable,
            "benchmarks/lineage_extractor/run.py",
            "--help",
        ],
        check=False,
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        text=True,
    )

    assert result.returncode == 0
    assert "Run lineage_extractor benchmark profiles." in result.stdout
