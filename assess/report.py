"""Console report formatting for assess results."""

from __future__ import annotations


def _fmt_table(
    headers: list[str],
    rows: list[list],
    col_widths: list[int],
) -> str:
    sep = "─" * (sum(col_widths) + len(col_widths) * 3 + 1)
    line = "│"
    for h, w in zip(headers, col_widths):
        line += f" {h:<{w}} │"
    lines = [line, f"├{sep}┤"]
    for row in rows:
        line = "│"
        for val, w in zip(row, col_widths):
            line += f" {str(val):<{w}} │"
        lines.append(line)
    return "\n".join(lines)


def generate_report(scores: dict, weights: dict, project: str) -> str:
    parts = []
    sep = "─" * 62

    overall_score = scores["overall_score"]
    parts.append(
        f"╔{'═' * 62}╗\n"
        f"║{'数据集市中间层评估报告':^62}║\n"
        f"║{'─' * 62}║\n"
        f"║{'项目: ' + project:<24}{'总体评分:':>18}{overall_score:>6.1f} / 100{' ' * 2}║\n"
        f"╠{'═' * 62}╣"
    )

    dims = [
        ("复用度", "reuse"),
        ("链路长度(中间层)", "depth"),
        ("模型设计", "model_design"),
        ("命名规范", "naming"),
        ("资产完整性", "asset_completeness"),
        ("模型元数据健康度", "metadata_health"),
        ("代码质量", "code_quality"),
    ]
    dimensions = scores["dimensions"]
    displayed_weight_total = sum(
        weights[key] for _, key in dims if key in dimensions and key in weights
    )
    for label, key in dims:
        if key not in dimensions:
            continue
        metric = dimensions[key]
        score = metric["score"]
        w = (
            weights[key] / displayed_weight_total * 100
            if displayed_weight_total
            else 0
        )
        parts.append(
            f"║ {label:<12} 评分:{score:>5.1f}  权重:{w:>2.0f}%{' ' * 24}║"
        )

    parts.append(f"╚{'═' * 62}╝")

    headers = ["规则ID", "规则", "严重度", "通过", "总计", "合规率"]
    col_w = [32, 28, 8, 6, 6, 8]
    for label, key in dims:
        if key not in dimensions:
            continue
        dimension = dimensions[key]
        parts.append(f"\n{'=' * 62}")
        parts.append(f"【{label}】评分: {dimension['score']}")
        parts.append(f"{'=' * 62}")

        rows = []
        for rule_id, counts in sorted(dimension["rule_summary"].items()):
            rows.append(
                [
                    rule_id,
                    counts["name"],
                    counts["severity"],
                    str(counts["pass_count"]),
                    str(counts["total"]),
                    f"{counts['pct']}%",
                ]
            )
        if not rows:
            rows.append(["(无检查项)", "", "", "0", "0", "0%"])
        parts.append(_fmt_table(headers, rows, col_w))

        issues = dimension["issues"]
        if issues:
            parts.append("\n  问题项:")
            for issue in issues[:30]:
                target = issue["target"]
                remediation = issue.get("remediation") or {}
                parts.append(
                    "    "
                    f"[{issue['severity']}] {issue['title']} | "
                    f"{target['type']}:{target['name']} | "
                    f"{issue['message']}"
                )
                if remediation.get("summary"):
                    parts.append(f"      建议: {remediation['summary']}")
            if len(issues) > 30:
                parts.append(f"    ... (共{len(issues)}个)")
        else:
            parts.append("\n  无问题项")
        parts.append(sep)

    parts.append(f"\n{'=' * 62}")
    return "\n".join(parts)
