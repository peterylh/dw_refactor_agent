# 字段重命名指南

## 前置规则

先阅读 [数仓资产重构通用规则](common.md)。

本指南只描述字段重命名特有流程；默认修改范围、派生文件处理、验证命令和不默认执行的操作，以通用规则为准。

## 目标

将 `{project}` 中指定表或链路里的字段从 `{old_column}` 重命名为 `{new_column}`，并保持 DDL、ETL SQL、模型元数据一致。

## 关键原则

字段重命名必须按表和血缘范围处理，不要对 `{old_column}` 做全局无脑替换。

先判断本次变更属于哪一种：

- 单表输出字段改名：只改变某张表对外暴露的字段名
- 上游输入字段改名：ODS 或源层字段改名，需要沿下游 SQL 引用传播
- 派生字段别名改名：表达式不变，只改变 `AS old_column` 的输出别名
- 语义变更：字段含义也改变，这不只是重命名，需要用户明确确认

如果只是字段重命名，不要改变字段类型、字段口径、聚合逻辑、分区逻辑、指标含义。

## 操作流程

### 1. 确认输入

先确认：

- `project`
- `table_name`
- `old_column`
- `new_column`
- 字段所在层级：ODS / DWD / DWS / DIM / ADS
- 是否只是字段名变化
- 是否需要向下游传播到依赖表

如果用户没有明确传播范围，默认按“该表输出字段改名，并修正真实下游引用”处理。

### 2. 搜索字段引用

先搜索字段名：

```bash
rg "<old_column>" warehouses/<project>
```

再结合表名搜索：

```bash
rg "<table_name>" warehouses/<project>
```

重点查看：

- `warehouses/{project}/mid/ddl/{table_name}.sql`
- 写入 `{table_name}` 的 task SQL
- 读取 `{table_name}` 的下游 task SQL
- `warehouses/{project}/mid/models/{table_name}.yaml`
- `warehouses/{project}/ods/data/`：仅 ODS 字段或初始化数据涉及该字段时

检查常见字段写法：

- `<old_column>`
- `` `<old_column>` ``
- `<alias>.<old_column>`
- `` `<alias>`.`<old_column>` ``
- `AS <old_column>`
- `` AS `<old_column>` ``

同名字段可能存在于多张表。修改前要结合 SQL 的 `FROM`、`JOIN`、表别名、CTE 输出列判断是否属于本次字段。

### 3. 修改 DDL

在 `warehouses/{project}/mid/ddl/{table_name}.sql` 中：

- 将字段定义名从 `{old_column}` 改为 `{new_column}`
- 保留字段类型、注释、默认值、聚合模型属性、Doris 属性
- 如果分区、分桶或 key 中引用了旧字段，同步改为新字段

不要因为字段改名而顺手调整字段顺序、类型、注释含义或表属性。

### 4. 修改写入该表的 ETL SQL

在写入 `{table_name}` 的 task SQL 中：

- `INSERT` 目标列清单里的 `{old_column}` 改为 `{new_column}`
- `SELECT ... AS old_column` 改为 `SELECT ... AS new_column`
- 如果表达式内部引用的是同一字段，也同步改名
- 如果表达式内部引用的是上游不同表的同名字段，不要误改

如果 SQL 没有显式 `INSERT` 目标列清单，应特别小心字段顺序。字段重命名不应该改变列数量或表达式顺序。

### 5. 修改下游读取引用

查找读取 `{table_name}` 的下游 SQL，将真实引用旧输出字段的地方改为新字段：

- `SELECT old_column`
- `WHERE old_column`
- `JOIN ... ON old_column`
- `GROUP BY old_column`
- `HAVING old_column`
- `ORDER BY old_column`
- 窗口函数中的 `PARTITION BY` / `ORDER BY`
- CTE、子查询、临时别名中的引用

如果下游 SQL 把旧字段继续暴露为同名输出字段，需要判断是否也应传播为 `{new_column}`。

不要修改其他来源表中的同名字段。

### 6. 修改 models YAML

models YAML 是项目的表级元数据源，不是普通文档。

在 `warehouses/{project}/mid/models/{table_name}.yaml` 中，只更新真实引用旧字段的配置项，例如：

- `atomic_metrics`
- `derived_metrics`
- `calculated_metrics`
- `dimensions`
- 其他已有字段级配置

如果 YAML 中没有旧字段引用，不要为了字段重命名新增新的 `columns` 结构。

保留原有：

- `name`
- `layer`
- `description`
- `config.materialized`
- `table_type`
- 其他未涉及本字段的配置

### 7. 修改初始化数据

只有当重命名的是 ODS 字段，或 `warehouses/{project}/ods/data/` 中明确引用旧字段时，才修改初始化数据 SQL。

不要为了 DWD/DWS/ADS 字段重命名去改无关 ODS 初始化数据。

### 8. 再次搜索残留

修改完成后运行：

```bash
rg "<old_column>" warehouses/<project>
```

同时按表名复核：

```bash
rg "<table_name>" warehouses/<project>
```

按照 [通用规则](common.md) 判断残留是否需要处理。

## 完成标准

字段重命名完成时，应满足：

- 目标表 DDL 字段名已更新
- 写入目标表的 task SQL 已更新
- 真实下游 SQL 字段引用已更新
- models YAML 中真实字段引用已更新
- 原有 models 表级元数据未丢失
- 初始化数据仅在确实涉及 ODS 字段时更新
- `rg "<old_column>" warehouses/<project>` 中没有未处理的真实字段引用
- `lineage_extractor.py --project <project>` 可正常解析
- 未默认修改工具代码、测试代码、HTML、lineage JSON、DAG JSON
