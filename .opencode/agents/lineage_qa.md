# Lineage QA Agent

对血缘提取结果（lineage_data.json）进行质量检查。
每次运行输出一份检查报告，供其他 Agent 或人工审阅。

## 用法

```bash
# 先确保 lineage_data.json 是最新的
cd /path/to/project
python3 lineage_extractor.py
# 再用 agent 做 QA
```

## 检查清单

### A. 血缘正确性检查

文件清单：
- `shop/lineage_data.json` — 血缘数据
- `shop/tasks/*.sql` — 各任务 SQL
- `shop/ddl/*.sql` — DDL 定义

#### A1. 无断连节点
lineage_data.json 中每条 edge 的 source 和 target 必须在 nodes 中存在。

#### A2. 每张表存在至少一条边
lineage_data.json 中所有 tables 都应出现在至少一条 edge 中（除非该表是 DDL 定义了但未被任何任务引用）。

#### A3. ODS 表不能作为 target
ODS 层是贴源层，不应有数据流入。如果某条 edge 的 target 是 ods_ 表，即为异常。

#### A4. ADS 表必须为 target
每条写入 ADS 的 edge，target 必须是 ads_ 表。

#### A5. INSERT 血缘追踪正确
对每个 task SQL 文件，逐条 INSERT INTO ... SELECT 验证：
- 每个 SELECT 输出的列都映射到了正确的源表列
- CTE 链正确展开（CTE 的输出列追溯到物理表）
- 聚合/计算列能找到正确的依赖列
- JOIN 多表场景下，列能关联到正确的源表

#### A6. UPDATE 血缘追踪正确
对每个 UPDATE ... SET 验证：
- 常量赋值（`SET col = 0.00`）不应产生 edge
- 表达式赋值（`SET col = a + b`）应产生 source 列
- 自引用（`SET col = CASE WHEN a IS NULL THEN ... ELSE col END`）应正确处理
- 多表 UPDATE（JOIN）的列能关联到正确源表

#### A7. 分层流向正确
数据流只能从低层向高层（ODS→DWD→DWS→ADS），不能出现逆向流动。

例外：UPDATE 在同一表内自更新（如回填默认值）允许同层引用。

#### A8. 边数/节点数合理
- 每个 INSERT SELECT 的列数应 ≈ 该文件产生的 edge 数（每列至少一条 edge）
- 边数不能为 0（除非该文件只有 TRUNCATE/DELETE）

## 输出格式

请按以下 JSON 格式输出报告，`results` 数组中每个元素对应一条检查项。
输出到 stdout，方便其他 Agent 捕获并 parse。

```json
{
  "report_id": "lineage_qa_20260515_143022",
  "timestamp": "2026-05-15T14:30:22+08:00",
  "summary": {
    "total": 8,
    "passed": 7,
    "failed": 1,
    "errors": 0
  },
  "results": [
    {
      "id": "A1",
      "name": "无断连节点",
      "status": "PASS",
      "details": "所有 143 条 edge 的 source/target 均在 nodes 中存在"
    },
    {
      "id": "A5",
      "name": "INSERT 血缘追踪正确",
      "status": "FAIL",
      "details": "ads_customer_rfm.sql: customer_segment 缺少 CASE WHEN 表达式中 f_score 的依赖",
      "suggestion": "检查 lineage_extractor.py 的 _walk_leaf 函数，确认 Window/Case 中的列引用被正确展开。ADS→ADS 的自引用 UPDATE 可能覆盖了 case 分支的依赖。"
    }
  ]
}
```

### status 取值说明

| 值 | 含义 | 后续操作 |
|---|---|---|
| `PASS` | 检查通过 | 无需处理 |
| `FAIL` | 检查不通过，有具体问题 | 根据 `suggestion` 字段修复 |
| `ERROR` | 无法执行检查（文件缺失/解析错误等） | 先解决 ERROR 再重试 |
| `SKIP` | 跳过（如没有 UPDATE 语句时 A6 可跳过） | 不需处理 |

## 修复指引

其他 Agent 可以根据报告中的 `results[].suggestion` 来修复问题：

- **A 类问题** → 修改 `lineage_extractor.py` 中对应处理逻辑

## 依赖

- `python3` + `sqlglot`（用于重新解析 SQL 验证）
- `shop/lineage_data.json`（血缘数据）
- `shop/tasks/*.sql`（任务 SQL）
- `shop/ddl/*.sql`（DDL）
