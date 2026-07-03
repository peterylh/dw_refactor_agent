# 表重命名指南

## 前置规则

先阅读 [数仓资产重构通用规则](common.md)。

本指南只描述表重命名特有流程；默认修改范围、派生文件处理、验证命令和不默认执行的操作，以通用规则为准。

## 目标

将 `{project}` 中的表从 `{old_table}` 重命名为 `{new_table}`，并保持 DDL、ETL SQL、模型元数据一致。

## 操作流程

### 1. 确认输入

先确认：

- `project`
- `old_table`
- `new_table`
- 是否只是物理表改名
- 是否同时改变表语义、层级或表类型

如果只是表重命名，不要改变 `layer`、`table_type`、`materialized`、指标分组等元数据含义。

### 2. 搜索旧表名

使用：

```bash
rg "<old_table>"
```

重点查看：

- DDL 文件
- task SQL 文件
- models YAML
- 上游或下游 SQL 引用
- 初始化数据 SQL，仅 ODS 表相关时

注意同时检查可能的库表限定写法：

- `<old_table>`
- `<db>.<old_table>`
- `` `<old_table>` ``
- `` `<db>`.`<old_table>` ``

### 3. 修改 DDL

如果存在 `warehouses/{project}/mid/ddl/{old_table}.sql`：

- 文件名改为 `{new_table}.sql`
- `CREATE TABLE` 表名改为 `{new_table}`
- 表内字段、注释、分区、Doris 属性默认保持不变

不要因为改表名而顺手调整字段、分区、模型语义。

### 4. 修改 ETL SQL

如果存在 `warehouses/{project}/mid/tasks/{old_table}.sql`：

- 文件名改为 `{new_table}.sql`
- `INSERT INTO old_table` 改为 `INSERT INTO new_table`
- 其他指向旧表的写入目标同步修改

然后修改所有上下游 SQL 中对旧表的读取引用。

只改真实表引用，不要盲目替换注释、历史说明或无关文本；是否更新注释取决于它是否描述当前逻辑。

### 5. 修改 models YAML

models YAML 是项目的表级元数据源，不是普通文档。

如果存在 `warehouses/{project}/mid/models/{old_table}.yaml`：

- 文件名改为 `{new_table}.yaml`
- YAML 内 `name: old_table` 改为 `name: new_table`
- 保留原有：
  - `layer`
  - `description`
  - `config.materialized`
  - `table_type`
  - `atomic_metrics`
  - `derived_metrics`
  - `calculated_metrics`
  - `dimensions`
  - 其他已有配置

原因：

- 表层级以 `models/*.yaml` 中的 `layer` 为权威来源
- `task_run.py --full-refresh` 会读取 `config.materialized`
- 血缘、重构验证、评估工具会依赖 models 元数据

### 6. 修改初始化数据

只有当重命名的是 ODS 表，或 `warehouses/{project}/ods/data/` 中明确引用旧表时，才修改初始化数据 SQL。

不要为了 DWD/DWS/ADS 表重命名去改无关 ODS 初始化数据。

### 7. 再次搜索残留

修改完成后运行：

```bash
rg "<old_table>"
```

按照 [通用规则](common.md) 判断残留是否需要处理。

## 完成标准

表重命名完成时，应满足：

- DDL 表名已更新
- 相关 task SQL 文件名和写入目标已更新
- 上下游 SQL 真实表引用已更新
- models YAML 文件名和 `name` 已更新
- 原有 models 元数据未丢失
- `rg "<old_table>"` 中没有未处理的真实表引用
- `lineage_extractor.py --project <project>` 可正常解析
- 未默认修改工具代码、测试代码、HTML、lineage JSON、DAG JSON
