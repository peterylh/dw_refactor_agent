"""Render lineage query results for humans and automation."""

from __future__ import annotations

import json
from collections import defaultdict

from lineage.query import ColumnLineage, ProjectStats, TableEdge, TableSubgraph


def _layer(subgraph: TableSubgraph, table: str) -> str:
    return subgraph.table_layers.get(table, "OTHER")


def _format_layers(layer_counts: dict[str, int]) -> str:
    return ", ".join(
        f"{layer}={count}" for layer, count in sorted(layer_counts.items())
    )


def _format_source_files(source_files: tuple[str, ...]) -> str:
    return ", ".join(source_files) if source_files else "-"


def _boundary_label(direction: str) -> str:
    if direction == "upstream":
        return "upstream tables"
    if direction == "downstream":
        return "downstream tables"
    return "lineage edges"


def _table_edge_maps(
    subgraph: TableSubgraph,
) -> tuple[dict[str, list[TableEdge]], dict[str, list[TableEdge]]]:
    by_target = defaultdict(list)
    by_source = defaultdict(list)
    for edge in subgraph.edges:
        by_target[edge.target].append(edge)
        by_source[edge.source].append(edge)
    for edges in by_target.values():
        edges.sort(key=lambda edge: (edge.hops, edge.source))
    for edges in by_source.values():
        edges.sort(key=lambda edge: (edge.hops, edge.target))
    return dict(by_target), dict(by_source)


def _format_upstream_tree(subgraph: TableSubgraph) -> list[str]:
    by_target, _by_source = _table_edge_maps(subgraph)
    lines = [f"  {subgraph.root} [{_layer(subgraph, subgraph.root)}]"]

    def visit(table: str, level: int, seen: set[str]) -> None:
        for edge in by_target.get(table, []):
            if edge.source in seen:
                continue
            indent = "  " + ("   " * level)
            lines.append(
                f"{indent}<- {edge.source} [{_layer(subgraph, edge.source)}]"
                f"  job={_format_source_files(edge.source_files)}"
            )
            visit(edge.source, level + 1, seen | {edge.source})

    visit(subgraph.root, 1, {subgraph.root})
    return lines


def _format_downstream_tree(subgraph: TableSubgraph) -> list[str]:
    _by_target, by_source = _table_edge_maps(subgraph)
    lines = [f"  {subgraph.root} [{_layer(subgraph, subgraph.root)}]"]

    def visit(table: str, level: int, seen: set[str]) -> None:
        for edge in by_source.get(table, []):
            if edge.target in seen:
                continue
            indent = "  " + ("   " * level)
            lines.append(
                f"{indent}-> {edge.target} [{_layer(subgraph, edge.target)}]"
                f"  job={_format_source_files(edge.source_files)}"
            )
            visit(edge.target, level + 1, seen | {edge.target})

    visit(subgraph.root, 1, {subgraph.root})
    return lines


def _format_tree(subgraph: TableSubgraph) -> list[str]:
    if subgraph.direction == "downstream":
        return _format_downstream_tree(subgraph)
    if subgraph.direction == "both":
        lines = _format_upstream_tree(subgraph)
        downstream = _format_downstream_tree(subgraph)[1:]
        if downstream:
            lines.append("  -- downstream --")
            lines.extend(downstream)
        return lines
    return _format_upstream_tree(subgraph)


def format_table_text(subgraph: TableSubgraph) -> str:
    """Render a table subgraph as terminal-friendly plain text."""
    lines = [
        f"Lineage: {subgraph.project} / {subgraph.root}",
        (
            f"Direction: {subgraph.direction}   Depth: {subgraph.depth}   "
            "Granularity: table"
        ),
        "",
        "Summary",
        (
            f"  Tables: {len(subgraph.tables)}   "
            f"Edges: {len(subgraph.edges)}   Jobs: {len(subgraph.jobs)}"
        ),
        f"  Layers: {_format_layers(subgraph.layer_counts)}",
    ]
    if subgraph.hidden_boundary_edges:
        lines.append(
            "  Boundary: reached depth limit, "
            f"{subgraph.hidden_boundary_edges} "
            f"{_boundary_label(subgraph.direction)} hidden"
        )
    else:
        lines.append("  Boundary: complete within requested depth")

    lines.extend(["", "Graph", *_format_tree(subgraph), "", "Edges"])
    lines.append("  source                  target                  hops  job")
    for edge in subgraph.edges:
        lines.append(
            f"  {edge.source:<23} {edge.target:<23} "
            f"{edge.hops:<5} {_format_source_files(edge.source_files)}"
        )
    return "\n".join(lines)


def _table_payload(subgraph: TableSubgraph) -> dict:
    return {
        "project": subgraph.project,
        "root": subgraph.root,
        "direction": subgraph.direction,
        "depth": subgraph.depth,
        "summary": {
            "tables": len(subgraph.tables),
            "edges": len(subgraph.edges),
            "jobs": len(subgraph.jobs),
            "layers": dict(sorted(subgraph.layer_counts.items())),
            "hidden_boundary_edges": subgraph.hidden_boundary_edges,
        },
        "tables": [
            {
                "name": table,
                "layer": _layer(subgraph, table),
                "columns": list(subgraph.table_columns.get(table, ())),
            }
            for table in sorted(subgraph.tables)
        ],
        "edges": [
            {
                "source": edge.source,
                "target": edge.target,
                "hops": edge.hops,
                "source_files": list(edge.source_files),
            }
            for edge in subgraph.edges
        ],
        "column_lineage": [
            {
                "source": row.source,
                "target": row.target,
                "expression": row.expression,
                "source_file": row.source_file,
                "transformation_type": row.transformation_type,
                "conditions": [
                    {
                        "source": condition.source,
                        "condition_type": condition.condition_type,
                        "condition_expression": condition.condition_expression,
                        "source_file": condition.source_file,
                    }
                    for condition in row.conditions
                ],
            }
            for row in subgraph.column_lineage
        ],
    }


def format_table_json(subgraph: TableSubgraph) -> str:
    return json.dumps(_table_payload(subgraph), ensure_ascii=False, indent=2)


def _dot_id(value: str) -> str:
    return json.dumps(value, ensure_ascii=False)


def format_table_dot(subgraph: TableSubgraph) -> str:
    lines = ["digraph lineage {"]
    for table in sorted(subgraph.tables):
        label = f"{table}\\n[{_layer(subgraph, table)}]"
        lines.append(f"  {_dot_id(table)} [label={_dot_id(label)}];")
    for edge in subgraph.edges:
        lines.append(f"  {_dot_id(edge.source)} -> {_dot_id(edge.target)};")
    lines.append("}")
    return "\n".join(lines)


def _format_transformations(transformation_counts: dict[str, int]) -> str:
    if not transformation_counts:
        return "-"
    return ", ".join(
        f"{name}={count}"
        for name, count in sorted(transformation_counts.items())
    )


def format_column_text(
    lineage: ColumnLineage, *, verbose: bool = False
) -> str:
    lines = [
        f"Column Lineage: {lineage.project} / {lineage.table}.{lineage.column}",
        f"Direction: {lineage.direction}   Depth: {lineage.depth}",
        "",
        "Summary",
        (
            f"  Paths: {len(lineage.paths)}   "
            f"Source Columns: {len(lineage.source_columns)}"
        ),
        (
            "  Transformations: "
            f"{_format_transformations(lineage.transformation_counts)}"
        ),
        (
            "  Source Files: "
            f"{', '.join(sorted(lineage.source_files)) if lineage.source_files else '-'}"
        ),
        "",
        "Paths",
    ]
    if not lineage.paths:
        lines.append("  -")
        return "\n".join(lines)

    for index, path in enumerate(lineage.paths):
        if index:
            lines.append("")
        lines.append(f"  {path.nodes[0]}")
        for step in path.steps:
            lines.extend(
                [
                    f"    -> {step.target}",
                    f"       expr: {step.expression or '-'}",
                    f"       job:  {step.source_file or '-'}",
                ]
            )
            if verbose and step.conditions:
                lines.append("       conditions:")
                for condition in step.conditions:
                    lines.append(
                        "         "
                        f"{condition.condition_type} {condition.source}: "
                        f"{condition.condition_expression or '-'}"
                    )
    return "\n".join(lines)


def _column_payload(lineage: ColumnLineage) -> dict:
    return {
        "project": lineage.project,
        "table": lineage.table,
        "column": lineage.column,
        "direction": lineage.direction,
        "depth": lineage.depth,
        "summary": {
            "paths": len(lineage.paths),
            "source_columns": len(lineage.source_columns),
            "source_files": sorted(lineage.source_files),
            "transformations": lineage.transformation_counts,
        },
        "paths": [
            {
                "nodes": list(path.nodes),
                "steps": [
                    {
                        "source": step.source,
                        "target": step.target,
                        "expression": step.expression,
                        "source_file": step.source_file,
                        "transformation_type": step.transformation_type,
                        "conditions": [
                            {
                                "source": condition.source,
                                "condition_type": condition.condition_type,
                                "condition_expression": (
                                    condition.condition_expression
                                ),
                                "source_file": condition.source_file,
                            }
                            for condition in step.conditions
                        ],
                    }
                    for step in path.steps
                ],
            }
            for path in lineage.paths
        ],
    }


def format_column_json(lineage: ColumnLineage) -> str:
    return json.dumps(_column_payload(lineage), ensure_ascii=False, indent=2)


def _stats_payload(stats: ProjectStats) -> dict:
    return {
        "project": stats.project,
        "summary": {
            "tables": stats.table_count,
            "table_edges": stats.table_edge_count,
            "column_edges": stats.column_edge_count,
            "indirect_edges": stats.indirect_edge_count,
            "jobs": stats.job_count,
            "layers": dict(sorted(stats.layer_counts.items())),
        },
    }


def format_stats_text(stats: ProjectStats) -> str:
    return "\n".join(
        [
            f"Lineage Stats: {stats.project}",
            "",
            "Summary",
            (
                f"  Tables: {stats.table_count}   "
                f"Table Edges: {stats.table_edge_count}   "
                f"Column Edges: {stats.column_edge_count}   "
                f"Jobs: {stats.job_count}"
            ),
            f"  Indirect Edges: {stats.indirect_edge_count}",
            f"  Layers: {_format_layers(stats.layer_counts)}",
        ]
    )


def format_stats_json(stats: ProjectStats) -> str:
    return json.dumps(_stats_payload(stats), ensure_ascii=False, indent=2)


def format_table_html(subgraph: TableSubgraph) -> str:
    payload = _table_payload(subgraph)
    lineage_json = json.dumps(payload, ensure_ascii=False, indent=2)
    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>Lineage: {subgraph.project} / {subgraph.root}</title>
  <style>
    body {{
      margin: 0;
      font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif;
      color: #1f2937;
      background: #f8fafc;
    }}
    header {{
      padding: 24px 32px 12px;
      border-bottom: 1px solid #d8dee8;
      background: #ffffff;
    }}
    h1 {{
      margin: 0 0 8px;
      font-size: 22px;
      font-weight: 650;
    }}
    .meta {{
      color: #5b6472;
      font-size: 13px;
    }}
    main {{
      padding: 24px 32px 32px;
    }}
    .summary {{
      display: flex;
      flex-wrap: wrap;
      gap: 12px;
      margin-bottom: 24px;
    }}
    .metric {{
      min-width: 128px;
      padding: 12px 14px;
      border: 1px solid #d8dee8;
      border-radius: 6px;
      background: #ffffff;
    }}
    .metric strong {{
      display: block;
      font-size: 20px;
    }}
    svg {{
      width: 100%;
      min-height: 360px;
      border: 1px solid #d8dee8;
      border-radius: 6px;
      background: #ffffff;
    }}
    .node rect {{
      fill: #ffffff;
      stroke: #334155;
      rx: 4;
    }}
    .node text {{
      fill: #111827;
      font-size: 12px;
    }}
    .edge {{
      stroke: #64748b;
      stroke-width: 1.4;
      marker-end: url(#arrow);
    }}
    .detail-grid {{
      display: grid;
      grid-template-columns: minmax(240px, 0.9fr) minmax(320px, 1.1fr);
      gap: 18px;
      margin-top: 22px;
      align-items: start;
    }}
    .panel {{
      border: 1px solid #d8dee8;
      border-radius: 6px;
      background: #ffffff;
      overflow: hidden;
    }}
    .panel h2 {{
      margin: 0;
      padding: 12px 14px;
      border-bottom: 1px solid #e5eaf2;
      font-size: 15px;
      font-weight: 650;
    }}
    .panel-body {{
      padding: 12px 14px;
    }}
    .table-card {{
      padding: 10px 0;
      border-bottom: 1px solid #edf1f7;
    }}
    .table-card:last-child {{
      border-bottom: 0;
    }}
    .table-name {{
      font-weight: 650;
    }}
    .tag {{
      display: inline-block;
      margin-left: 6px;
      padding: 1px 6px;
      border: 1px solid #cbd5e1;
      border-radius: 999px;
      color: #475569;
      font-size: 11px;
      line-height: 16px;
    }}
    .columns {{
      margin-top: 6px;
      color: #475569;
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 12px;
      line-height: 1.5;
      word-break: break-word;
    }}
    table {{
      width: 100%;
      border-collapse: collapse;
      font-size: 12px;
    }}
    th, td {{
      padding: 8px 6px;
      border-bottom: 1px solid #edf1f7;
      text-align: left;
      vertical-align: top;
    }}
    th {{
      color: #475569;
      font-weight: 650;
      background: #f8fafc;
    }}
    code {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 12px;
    }}
    .lineage-row {{
      padding: 12px 0;
      border-bottom: 1px solid #edf1f7;
    }}
    .lineage-row:last-child {{
      border-bottom: 0;
    }}
    .lineage-title {{
      font-family: ui-monospace, SFMono-Regular, Menlo, monospace;
      font-size: 12px;
      font-weight: 650;
    }}
    .expr {{
      margin-top: 7px;
      padding: 8px;
      border-radius: 4px;
      background: #f8fafc;
      color: #334155;
      white-space: pre-wrap;
      word-break: break-word;
    }}
    .conditions {{
      margin-top: 8px;
      padding-left: 16px;
      color: #475569;
      font-size: 12px;
    }}
    .conditions li {{
      margin: 4px 0;
    }}
  </style>
</head>
<body>
  <header>
    <h1>{subgraph.root}</h1>
    <div class="meta">{subgraph.project} · {subgraph.direction} · depth {subgraph.depth}</div>
  </header>
  <main>
    <section class="summary" id="summary"></section>
    <svg id="graph" role="img" aria-label="local lineage graph"></svg>
    <section class="detail-grid">
      <section class="panel">
        <h2>Tables And Columns</h2>
        <div class="panel-body" id="tables"></div>
      </section>
      <section class="panel">
        <h2>Table Edges</h2>
        <div class="panel-body" id="edges"></div>
      </section>
    </section>
    <section class="panel" style="margin-top: 18px;">
      <h2>Column Lineage</h2>
      <div class="panel-body" id="column-lineage"></div>
    </section>
  </main>
  <script>
    const LINEAGE_DATA = {lineage_json};
    const escapeHtml = (value) => String(value ?? "").replace(/[&<>"']/g, (char) => ({{
      "&": "&amp;",
      "<": "&lt;",
      ">": "&gt;",
      '"': "&quot;",
      "'": "&#39;",
    }}[char]));

    const summary = document.getElementById("summary");
    const metrics = [
      ["Tables", LINEAGE_DATA.summary.tables],
      ["Edges", LINEAGE_DATA.summary.edges],
      ["Jobs", LINEAGE_DATA.summary.jobs],
      ["Hidden", LINEAGE_DATA.summary.hidden_boundary_edges],
    ];
    summary.innerHTML = metrics.map(([label, value]) =>
      `<div class="metric"><strong>${{value}}</strong>${{label}}</div>`
    ).join("");

    const svg = document.getElementById("graph");
    const width = Math.max(720, svg.clientWidth || 720);
    const layerOrder = ["ODS", "DIM", "DWD", "DWS", "ADS", "OTHER"];
    const tables = [...LINEAGE_DATA.tables].sort((a, b) => {{
      const layerDelta = layerOrder.indexOf(a.layer) - layerOrder.indexOf(b.layer);
      return layerDelta || a.name.localeCompare(b.name);
    }});
    const grouped = new Map();
    tables.forEach((table) => {{
      if (!grouped.has(table.layer)) grouped.set(table.layer, []);
      grouped.get(table.layer).push(table);
    }});
    const layers = [...grouped.keys()].sort(
      (a, b) => layerOrder.indexOf(a) - layerOrder.indexOf(b)
    );
    const xGap = Math.max(180, Math.floor((width - 160) / Math.max(1, layers.length - 1)));
    const positions = new Map();
    layers.forEach((layer, layerIndex) => {{
      grouped.get(layer).forEach((table, rowIndex) => {{
        positions.set(table.name, {{
          x: 60 + layerIndex * xGap,
          y: 56 + rowIndex * 86,
          layer,
        }});
      }});
    }});
    const maxRows = Math.max(...[...grouped.values()].map((items) => items.length), 1);
    svg.setAttribute("viewBox", `0 0 ${{width}} ${{Math.max(360, 120 + maxRows * 86)}}`);
    svg.innerHTML = `
      <defs>
        <marker id="arrow" markerWidth="8" markerHeight="8" refX="7" refY="3"
          orient="auto" markerUnits="strokeWidth">
          <path d="M0,0 L0,6 L7,3 z" fill="#64748b"></path>
        </marker>
      </defs>
    `;
    LINEAGE_DATA.edges.forEach((edge) => {{
      const source = positions.get(edge.source);
      const target = positions.get(edge.target);
      if (!source || !target) return;
      svg.insertAdjacentHTML("beforeend",
        `<line class="edge" x1="${{source.x + 140}}" y1="${{source.y + 18}}"
          x2="${{target.x}}" y2="${{target.y + 18}}"></line>`
      );
    }});
    tables.forEach((table) => {{
      const point = positions.get(table.name);
      svg.insertAdjacentHTML("beforeend", `
        <g class="node" transform="translate(${{point.x}}, ${{point.y}})">
          <rect width="140" height="42"></rect>
          <text x="10" y="17">${{table.name}}</text>
          <text x="10" y="33">[${{table.layer}}]</text>
        </g>
      `);
    }});

    document.getElementById("tables").innerHTML = tables.map((table) => `
      <div class="table-card">
        <div class="table-name">${{escapeHtml(table.name)}}<span class="tag">${{escapeHtml(table.layer)}}</span></div>
        <div class="columns">${{table.columns.length ? table.columns.map(escapeHtml).join(", ") : "-"}}</div>
      </div>
    `).join("");

    document.getElementById("edges").innerHTML = `
      <table>
        <thead><tr><th>Source</th><th>Target</th><th>Hops</th><th>Job</th></tr></thead>
        <tbody>
          ${{LINEAGE_DATA.edges.map((edge) => `
            <tr>
              <td><code>${{escapeHtml(edge.source)}}</code></td>
              <td><code>${{escapeHtml(edge.target)}}</code></td>
              <td>${{escapeHtml(edge.hops)}}</td>
              <td>${{escapeHtml((edge.source_files || []).join(", ") || "-")}}</td>
            </tr>
          `).join("")}}
        </tbody>
      </table>
    `;

    document.getElementById("column-lineage").innerHTML = LINEAGE_DATA.column_lineage.length
      ? LINEAGE_DATA.column_lineage.map((row) => `
        <div class="lineage-row">
          <div class="lineage-title">${{escapeHtml(row.source)}} -> ${{escapeHtml(row.target)}}</div>
          <div class="meta">${{escapeHtml(row.transformation_type)}} · ${{escapeHtml(row.source_file || "-")}}</div>
          <div class="expr">${{escapeHtml(row.expression || "-")}}</div>
          ${{row.conditions && row.conditions.length ? `
            <ul class="conditions">
              ${{row.conditions.map((condition) => `
                <li><code>${{escapeHtml(condition.condition_type)}} ${{escapeHtml(condition.source)}}</code>: ${{escapeHtml(condition.condition_expression || "-")}}</li>
              `).join("")}}
            </ul>
          ` : ""}}
        </div>
      `).join("")
      : "<div class=\\"meta\\">No local column lineage in this subgraph.</div>";
  </script>
</body>
</html>
"""
