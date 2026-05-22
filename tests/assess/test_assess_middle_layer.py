from assess.assess_middle_layer import assess, generate_report, map_dep_health_display


def test_map_dep_health_display_uses_piecewise_mapping():
    assert map_dep_health_display(0) == 0.0
    assert map_dep_health_display(60) == 30.0
    assert map_dep_health_display(80) == 55.0
    assert map_dep_health_display(90) == 75.0
    assert map_dep_health_display(95) == 85.0
    assert map_dep_health_display(100) == 100.0


def test_assess_returns_raw_and_display_scores(monkeypatch, sample_lineage_data):
    monkeypatch.setattr(
        "assess.assess_middle_layer.load_lineage_data",
        lambda project: sample_lineage_data,
    )

    result = assess(project="shop")

    assert "dep_health" in result
    assert "health" not in result
    assert result["weights"]["dep_health"] == 0.25

    assert result["reuse"]["raw"] == result["reuse"]["display"]
    assert result["depth"]["raw"] == result["depth"]["display"]
    assert result["naming"]["raw"] == result["naming"]["display"]

    assert result["dep_health"]["raw"] == 95
    assert result["dep_health"]["display"] == 85.0
    assert result["overall_display"] < result["overall_raw"]


def test_generate_report_contains_raw_and_display_scores(
        monkeypatch, sample_lineage_data):
    monkeypatch.setattr(
        "assess.assess_middle_layer.load_lineage_data",
        lambda project: sample_lineage_data,
    )

    result = assess(project="shop")
    report = generate_report(result, result["weights"], "shop")

    assert "总体评分(展示)" in report
    assert "总体评分(原始)" in report
    assert "【依赖健康度】评分(展示/原始): 85.0 / 95" in report
    assert "累计扣分: 5" in report
