from refact.issue_diff import diff_assess_results


def _issue(fingerprint, title):
    return {
        "fingerprint": fingerprint,
        "title": title,
        "target": {"type": "table", "name": title},
    }


def test_diff_assess_results_classifies_fixed_remaining_and_new():
    baseline = {
        "overall_score": 50.0,
        "dimensions": {
            "naming": {
                "score": 50.0,
                "issues": [
                    _issue("a", "old-a"),
                    _issue("b", "old-b"),
                ],
            }
        },
    }
    current = {
        "overall_score": 90.0,
        "dimensions": {
            "naming": {
                "score": 90.0,
                "issues": [
                    _issue("b", "new-b"),
                    _issue("c", "new-c"),
                ],
            }
        },
    }

    result = diff_assess_results(baseline, current)

    assert result["summary"] == {
        "baseline_issue_count": 2,
        "current_issue_count": 2,
        "fixed_count": 1,
        "remaining_count": 1,
        "new_count": 1,
    }
    assert [issue["fingerprint"] for issue in result["fixed_issues"]] == ["a"]
    assert [issue["fingerprint"] for issue in result["remaining_issues"]] == [
        "b"
    ]
    assert [issue["fingerprint"] for issue in result["new_issues"]] == ["c"]
    assert result["scope_score"]["overall_score"] == 90.0
    assert result["scope_score"]["dimensions"]["naming"]["score"] == 90.0
