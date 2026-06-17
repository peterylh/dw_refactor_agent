# SQL 数据开发规范

## 1. 分层与命名

### 数据分层

| 层   | 职责                     | 表名前缀 | 示例                     |
|------|--------------------------|----------|--------------------------|
| ODS  | 贴源层，与源系统结构一致    | `ods_`   | `ods_order`              |
| DWD  | 明细宽表层，清洗 + 维度关联 | `dwd_`   | `dwd_order_detail`       |
| DWS  | 汇总层，轻度聚合，面向主题  | `dws_`   | `dws_store_sales_daily`  |
| ADS  | 应用层，面向报表 / 看板    | `ads_`   | `ads_sales_dashboard`    |

### 表命名规范

- **格式**: `{层前缀}_{主题}[_{修饰}]`，全小写，下划线分隔
- **语义清晰**: 表名能让人一眼看出它属于哪一层、描述什么主题
- **文件名 = 表名**: DDL 文件和 ETL 作业文件均以目标表名命名（如 `dwd_customer.sql`）

### 字段命名规范

- 全小写，下划线分隔，禁止缩写歧义（`qty` ✓，`q` ✗）
- 主键字段：`{实体}_id`（如 `order_id`、`customer_id`）
- 时间字段：`{语义}_time`（时间戳）或 `{语义}_date`（日期）
- 金额字段：`{语义}_amount`（如 `total_amount`、`discount_amount`）
- 标志字段：`is_{状态}`（如 `is_deleted`、`is_active`）
- ETL 附加字段：`etl_time`（加工时间戳）、`snapshot_date`（快照日期）

---

## 2. DDL 编写规范

### 建表模板

```sql
-- {层} {表中文说明}
-- table_id: uuid
DROP TABLE IF EXISTS {db}.{table_name};
CREATE TABLE IF NOT EXISTS {db}.{table_name} (
    id BIGINT NOT NULL COMMENT 'ID',
    ...
) ENGINE=OLAP
DUPLICATE KEY(id)
DISTRIBUTED BY HASH(id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
```

### 要点

- 文件头注释说明表用途、主键、数据类型、金额字段等
- table_id 为 UUID4 字符串, 不要编辑table_id
- 主键列 `NOT NULL`，附中文 COMMENT
- 枚举值在 COMMENT 中列出可选值（如 `COMMENT '状态: 已完成/已取消'`）
- 数据类型优先级：`BIGINT` > `DECIMAL(12,2)` > `DATE/DATETIME` > `VARCHAR(n)`
- 金额统一 `DECIMAL(12,2) DEFAULT '0.00'`
- ODS 初始化数据单独放 `{project}/ods/data/{catalog}/{database}/` 目录，DDL 文件只含结构



## 3. ETL 作业编写规范

### 作业模板

```sql
-- 加工作业: {层} {表中文说明}
-- 目标表: {db}.{target_table}
-- 源表: {source_tables}
-- 加工逻辑: {一句话描述}

TRUNCATE TABLE {db}.{target_table};

INSERT INTO {db}.{target_table}
SELECT ...
FROM {db}.{source_a} a
LEFT JOIN {db}.{source_b} b ON a.id = b.id;
```

### 要点

- 头部注释写清目标表、源表、加工逻辑摘要
- `NOW() AS etl_time` 记录加工时间
- JOIN 策略：LEFT JOIN 优先，避免数据丢失
- GROUP BY 仅在 DWS / ADS 层使用

---

## 4. 编码原则

### 可读性

- **表达意图，不表达步骤**：SQL 应让读者理解"做什么"而非"怎么做"
- **合理注释**：解释"为什么"，不解释"是什么"。复杂业务逻辑、非直觉的 JOIN 条件、特殊的数据处理必须注释
- **保持简单**：一个作业做一件事。如果 SQL 超过 100 行，考虑是否该拆分

### 可维护性

- **一表一文件**：DDL、ETL 作业均与目标表一一对应
- **不重复自己**：相同逻辑不要复制粘贴到多个作业，考虑提取到中间层
- **分层依赖单向**：只能引用同层或上一层的表，禁止跨层引用（如 ADS 直接读 ODS）

### 性能

- **减少全表扫描**：WHERE 条件尽量命中分区列
- **控制 JOIN 数量**：单个 SQL 建议不超过 5 张表 JOIN
- **避免 SELECT \***：显式列出所需字段
- **慎用子查询**：优先用 JOIN 或 CTE 改写关联子查询

### 可测试性

- **幂等设计**：相同输入 + 相同 `@etl_date`，任意重跑结果一致
- **参数化日期**：使用 `@etl_date` 变量，支持历史数据重跑
- **可血缘追踪**：所有字段加工逻辑可被 sqlglot lineage 工具解析
