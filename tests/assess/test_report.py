import unicodedata

from dw_refactor_agent.assessment.report import _fmt_table, generate_report


def _display_width(text):
    width = 0
    for char in text:
        if unicodedata.combining(char):
            continue
        if unicodedata.east_asian_width(char) in {"F", "W"}:
            width += 2
        else:
            width += 1
    return width


def _separator_offsets(line):
    offsets = []
    width = 0
    for char in line:
        if char == "│":
            offsets.append(width)
        width += _display_width(char)
    return offsets


def _expected_separator_offsets(headers, rows, minimum_widths):
    widths = []
    for index, minimum_width in enumerate(minimum_widths):
        values = [headers[index]] + [row[index] for row in rows]
        widths.append(
            max(
                minimum_width,
                *[_display_width(str(value)) for value in values],
            )
        )

    offsets = [0]
    for width in widths:
        offsets.append(offsets[-1] + width + 3)
    return offsets


def test_fmt_table_aligns_separator_columns_with_chinese_text():
    headers = ["规则ID", "规则", "严重度", "通过", "总计", "合规率"]
    rows = [
        [
            "CODE_FILTER_COLUMN_WRAPPED_IN_FUNCTION",
            "过滤列不被函数或CAST包裹",
            "高",
            "0",
            "6",
            "0.0%",
        ],
        [
            "CODE_NO_SELECT_STAR_IN_WRITE",
            "写入型语句不使用SELECT *",
            "高",
            "25",
            "26",
            "96.2%",
        ],
    ]
    minimum_widths = [36, 32, 8, 6, 6, 8]

    table = _fmt_table(
        headers=headers,
        rows=rows,
        col_widths=minimum_widths,
    )

    lines = [line for line in table.splitlines() if line.startswith("│")]
    expected_offsets = _expected_separator_offsets(
        headers, rows, minimum_widths
    )

    assert lines
    for line in lines:
        assert _separator_offsets(line) == expected_offsets


def _quarantined_report(score, effective_score, status, eligible, assessed):
    return generate_report(
        {
            "overall_score": effective_score,
            "dimensions": {
                "reuse": {
                    "score": score,
                    "effective_score": effective_score,
                    "status": status,
                    "complete": False,
                    "coverage": {
                        "unit": "tables",
                        "eligible_count": eligible,
                        "assessed_count": assessed,
                    },
                    "rule_summary": {},
                    "issues": [],
                }
            },
        },
        {"reuse": 1.0},
        "shop",
    )


def test_report_discloses_partial_and_unassessed_quarantine():
    report = _quarantined_report(100.0, 50.0, "quarantined", 2, 1)
    assert "【复用度】计入总分: 50.0" in report
    assert "已评估部分得分: 100.0" in report
    assert "评估覆盖: 1/2 tables，状态=quarantined" in report
    assert "隔离语义未参与评估" in report

    not_assessed = _quarantined_report(None, 0.0, "not_assessed", 1, 0)
    assert "评分:  N/A" in not_assessed
    assert "【复用度】评分: N/A" in not_assessed
    assert "总分贡献: 0.0" in not_assessed
    assert "已评估部分得分: None" not in not_assessed
