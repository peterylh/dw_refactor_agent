# Lineage HTML & DB QA Agent

对血缘 HTML 可视化界面和 Doris 数据库中血缘数据进行质量检查。
每次运行输出一份检查报告，供其他 Agent 或人工审阅。

## 用法

```bash
# 先确保 lineage_data.json 是最新的
cd /path/to/project
python3 lineage_extractor.py
python3 refresh_lineage_html.py
python3 import_lineage.py
# 再用 agent 做 QA
```

## 检查清单

### B. HTML 界面检查

文件清单：
- `shop/lineage_job.html` — 作业级 + 字段级双视图
- `shop/lineage.html` — 字段级视图
- `shop/lineage_data.json` — 数据源

#### B1. HTML 包含正确的数据
- `lineage_job.html` 中的 `const LD` 数据必须与 `lineage_data.json` 一致
- `lineage_job.html` 中的 `const JOBS` 必须覆盖所有 task SQL 文件
- `lineage.html` 中的 `const LINEAGE_DATA` 必须与 `lineage_data.json` 一致

#### B2. 数据注入语法正确
- `const LD = {...}` — JSON 必须有效，不能截断
- `const JOBS = [...]` — 数组必须完整闭合
- HTML 文件必须能在浏览器中打开不报 JS 语法错误

#### B3. 作业级视图可用
`lineage_job.html` 在「作业级视图」模式下：
- ODS / DWD / DWS / ADS 四个层级列正确排列
- 每个层级的表节点可见，表名、列数正确
- 作业节点（紫色胶囊形）显示在对应层级之间
- 源表 → 作业 → 目标表 的连线正确
- 搜索/筛选/适应画面/导出按钮功能正常
- 点击作业节点，右侧面板显示作业详情（源表、目标表、加工逻辑）
- 双击表节点切换到字段级视图

#### B4. 字段级视图可用
`lineage_job.html` 在「字段级视图」模式下：
- 层级列正确排列
- 点击表头可展开/折叠
- 展开后显示列名和类型
- 字段级连线可见，颜色正确
- 点击连线显示转换表达式
- 点击字段显示上游/下游血缘

#### B5. 字段级视图 `lineage.html` 可用
- `<script>` 标签内的数据正确注入
- SVG 渲染正常
- 搜索/筛选/展开折叠功能正常
- 右侧面板在点击节点或连线时显示正确详情

#### B6. 色系一致
- ODS = 绿色 `#52c41a`
- DWD = 蓝色 `#1890ff`
- DWS = 橙色 `#fa8c16`
- ADS = 红色 `#f5222d`

#### B7. JS 无错误
在浏览器 DevTools Console 中不应有 JS 错误：
- 不能有 `Uncaught TypeError`
- 不能有 `undefined is not an object`
- 不能有空 JSON 导致的 SVG 渲染失败

### C. Doris 数据库检查

文件清单：
- `shop/lineage_data.json` — 血缘数据
- `shop/tasks/*.sql` — 各任务 SQL
- `shop/ddl/*.sql` — DDL 定义
- Doris 数据库 `lineage`（`import_lineage.py` 定义的目标库）

前置条件：已运行 `python3 import_lineage.py` 将数据导入 Doris。

#### C1. Doris 连接可用
能通过 pymysql 连接到 Doris（host: 172.16.0.90, port: 9030, database: lineage）。

#### C2. 字段级血缘数量一致
`column_lineage` 表中的记录数应与 `lineage_data.json` 中的 edges 数一致。

#### C3. 表级血缘数量一致
`table_lineage` 表中的关系数应与从 edges 推导出的唯一 (source_table, target_table) 对数量一致。

#### C4. 作业覆盖完整
`job` 表中的记录应覆盖 `shop/tasks/` 目录下所有 SQL 文件。每个 SQL 文件应有且仅有一条 job 记录。

#### C5. 列元数据覆盖 DDL
- `table_info` 中的表应覆盖所有有 DDL 定义且被任务引用的表
- `column_info` 中的列应覆盖 `lineage_data.json` 中 tables 下的所有 columns
- `column_info` 中的 data_type 不应为 `UNKNOWN`（`lineage_extractor.py` 的默认值，应该在导入 Doris 前已被 DDL 类型覆盖）

#### C6. 字段级血缘引用有效
`column_lineage` 中的所有 `source_column_id` 和 `target_column_id` 必须在 `column_info` 中存在。不允许有悬挂引用。

#### C7. 表级血缘引用有效
`table_lineage` 中的所有 `source_table_id` 和 `target_table_id` 必须在 `table_info` 中存在。不允许有悬挂引用。

#### C8. 分层信息正确
`table_info` 中每张表的 `layer` 字段必须与 `lineage_data.json` 中该表的 layer 一致。

## 输出格式

请按以下 JSON 格式输出报告，`results` 数组中每个元素对应一条检查项。
输出到 stdout，方便其他 Agent 捕获并 parse。

```json
{
  "report_id": "html_db_qa_20260515_143022",
  "timestamp": "2026-05-15T14:30:22+08:00",
  "summary": {
    "total": 15,
    "passed": 13,
    "failed": 1,
    "errors": 1
  },
  "results": [
    {
      "id": "B1",
      "name": "HTML 包含正确的数据",
      "status": "PASS",
      "details": "LD 数据一致: 159 nodes, 143 edges"
    },
    {
      "id": "C1",
      "name": "Doris 连接可用",
      "status": "FAIL",
      "details": "无法连接 Doris: (2003, \"Can't connect to MySQL server on '172.16.0.90:9030' (60)\")",
      "suggestion": "请确认 Doris 服务是否运行，网络是否可达。运行 python3 import_lineage.py 重新导入。"
    },
    {
      "id": "C2",
      "name": "字段级血缘数量一致",
      "status": "ERROR",
      "details": "数据库不可用，跳过检查"
    }
  ]
}
```

### status 取值说明

| 值 | 含义 | 后续操作 |
|---|---|---|
| `PASS` | 检查通过 | 无需处理 |
| `FAIL` | 检查不通过，有具体问题 | 根据 `suggestion` 字段修复 |
| `ERROR` | 无法执行检查（文件缺失/解析错误/DB不可用等） | 先解决 ERROR 再重试 |
| `SKIP` | 跳过（如 Doris 不可用时 C 系列检查可跳过） | 不需处理 |

## 修复指引

其他 Agent 可以根据报告中的 `results[].suggestion` 来修复问题：

- **B 类问题** → 运行 `python3 refresh_lineage_html.py` 重新注入数据，或手动修改 HTML
- **C 类问题** → 运行 `python3 import_lineage.py` 重新导入，或检查 Doris 连接配置

## 依赖

- `python3` + `pymysql`（用于连接 Doris）
- `shop/lineage_data.json`（血缘数据）
- `shop/tasks/*.sql`（任务 SQL）
- `shop/ddl/*.sql`（DDL）
- `shop/lineage_job.html`（HTML 可视化）
- `shop/lineage.html`（HTML 可视化）
- Doris 数据库 `lineage`（host: 172.16.0.90:9030）
