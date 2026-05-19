# shop-dm

## 项目概述

零售门店数据仓库建模项目。基于 Doris 构建经典分层数据仓库,并配
套字段级 SQL 血缘提取与可视化工具。

包含两个子项目:
- **shop**: 零售门店数据仓库
- **olist**: 巴西电商(Olist)数据仓库, 基于公开 Kaggle 数据集

## 技术栈

- **血缘提取**: sqlglot提供了 lineage 方法
- **Doris连接**: mysql -h172.16.0.90 -P9030 -uroot

## 目录结构

```
shop-dm/
├── ddl_deriver/             # DDL 变更自动推导工具
│   ├── __init__.py
│   └── ddl_deriver.py       # 核心: DDL 解析 + 变更推导引擎
├── shop/
│   ├── ddl/                 # 各层表结构定义 (含 INIT DML)
│   │   ├── ods_*.sql        # ODS 贴源层
│   │   ├── dwd_*.sql        # DWD 明细层
│   │   ├── dws_*.sql        # DWS 汇总层
│   │   └── ads_*.sql        # ADS 应用层
│   └── tasks/               # ETL 加工作业 SQL
│       ├── dwd_*.sql        # ods → dwd 加工
│       ├── dws_*.sql        # dwd → dws 加工
│       └── ads_*.sql        # dws → ads 加工
├── olist/                   # 巴西电商(Olist)数据仓库 (结构同 shop/)
│   ├── ddl/                 # 表结构定义 (库前缀 olist_dm.)
│   │   ├── ods_*.sql        # 9 张 ODS 表
│   │   ├── dwd_*.sql        # 4 张 DWD 纯维度表
│   │   ├── dws_*.sql        # 4 张 DWS 汇总表
│   │   └── ads_*.sql        # 7 张 ADS 应用表
│   ├── tasks/               # ETL 加工作业
│   │   ├── dwd_*.sql        # 4 个 DWD 任务
│   │   ├── dws_*.sql        # 4 个 DWS 任务
│   │   └── ads_*.sql        # 7 个 ADS 任务
│   ├── download_data.py     # 从 Kaggle 下载 Olist 数据集
│   ├── import_data.py       # Stream Load 导入 CSV → Doris
│   ├── lineage.html         # 表/列级血缘可视化
│   └── lineage_job.html     # 作业级血缘可视化
├── lineage/
│   ├── __init__.py
│   ├── ddl/                 # lineage 库表结构定义
│   │   ├── datasource.sql
│   │   ├── table_info.sql
│   │   ├── column_info.sql
│   │   ├── job.sql
│   │   ├── column_lineage.sql
│   │   ├── indirect_lineage.sql
│   │   └── table_lineage.sql
│   ├── lineage_extractor.py # SQL 字段级血缘抽取引擎
│   ├── import_lineage.py    # 血缘数据导入 lineage 库
│   ├── refresh_lineage_html.py # HTML 刷新工具
│   ├── lineage_data.json    # 血缘中间数据
│   ├── lineage.html         # 表/列级血缘可视化
│   └── lineage_job.html     # 作业级血缘可视化
├── tests/
│   ├── __init__.py
│   ├── conftest.py          # 共享 fixture
│   ├── ddl_deriver/         # DDL 推导相关测试
│   │   ├── __init__.py
│   │   ├── test_ddl_deriver.py
│   │   └── verify_doris_a.py
│   └── lineage/             # 血缘提取相关测试
│       ├── __init__.py
│       ├── test_build_schema.py
│       ├── test_extract_lineage.py
│       ├── test_layer_function.py
│       ├── test_trace_lineage.py
│       └── test_update_to_select.py
├── AGENTS.md
└── commit_message.md        # Git Commit 规范

- ../sqlglot/是SQLglot代码目录， 可用于研究 sqlglot实现原理和使用方式

```

## 分层命名规范

| 层   | 含义                     | 表名前缀 | 示例                     |
|------|--------------------------|----------|--------------------------|
| ODS  | 贴源层,与源系统结构一致    | `ods_`   | `ods_order`              |
| DWD  | 明细宽表层,清洗+维度关联   | `dwd_`   | `dwd_order_detail`       |
| DWS  | 服务层,轻度聚合,面向主题   | `dws_`   | `dws_store_sales_daily`  |
| ADS  | 应用层,面向具体报表/看板   | `ads_`   | `ads_sales_dashboard`    |

shop 项目: 库名前缀 `shop_dm.`
olist 项目: 库名前缀 `olist_dm.`

## DDL 编写规范

- 引擎: `ENGINE=OLAP`, DUPLICATE KEY 取主键第一列, HASH 分桶数 10, 单副本
- 主键: `NOT NULL COMMENT '中文说明'`, 数值型 BIGINT > DECIMAL(12,2) > DATE/DATETIME
- 字符串: `VARCHAR(n)` 可 NULL, 枚举值用 COMMENT 说明 (例: `COMMENT '状态:已完成/已取消'`)
- 金额: `DECIMAL(12,2)` 默认 0.00
- DDL 中包含真实度高的 INIT 示例数据 (INSERT INTO ... VALUES)
- 文件头加注释说明表用途: `-- ODS xxxx表`

DDL 模板:
```sql
-- ODS xxxx表
DROP TABLE IF EXISTS shop_dm.ods_xxx;
CREATE TABLE IF NOT EXISTS shop_dm.ods_xxx (
    id BIGINT NOT NULL COMMENT 'ID',
    ...
) ENGINE=OLAP
DUPLICATE KEY(id)
DISTRIBUTED BY HASH(id) BUCKETS 10
PROPERTIES ("replication_num" = "1");

INSERT INTO shop_dm.ods_xxx VALUES ...;
```

## ETL 任务编写规范

- 文件名与目标表同名 (例: `dwd_customer.sql` → `shop_dm.dwd_customer`)
- 开头: TRUNCATE TABLE 清空目标表
- 核心: `INSERT INTO ... SELECT ... FROM` 关联多表 + 字段计算
- 宽表策略: 多表 JOIN, LEFT JOIN 优先于 INNER JOIN, 建表维度先行
- 增量字段: `NOW() AS etl_time` 记录加工时间
- NULL 回填: UPDATE 分步完成,每步 SET 1-2 列,后续 JOIN 加提示性注释
- 维度表: 少量维表逻辑 JOIN 处理中嵌入, 禁止 UNION ALL DML; GROUP BY 仅 dws/ads 使用
- 头部写清楚: 目标, 源表, 加工逻辑

模板:
```sql
-- 加工作业: DWD xxx表
-- 源表: ods_a, ods_b
-- 加工逻辑: 关联 -> 计算 -> 回填

TRUNCATE TABLE shop_dm.dwd_xxx;

INSERT INTO shop_dm.dwd_xxx
SELECT ... FROM shop_dm.ods_a a
LEFT JOIN shop_dm.ods_b b ON a.id = b.id;

UPDATE shop_dm.dwd_xxx SET col = default WHERE col IS NULL;
```

## 血缘工具

### lineage_extractor.py

字段级血缘解析引擎。读取 `shop/ddl/` 的建表语句和 `shop/tasks/` 的 ETL SQL, 输出 `lineage/lineage_data.json`:

支持 `--project shop|olist` 参数:
```bash
# shop 项目 (默认)
python lineage/lineage_extractor.py
# olist 项目
python lineage/lineage_extractor.py --project olist
```

### import_lineage.py

将 `lineage_data_{project}.json` 导入到 Doris 对应项目的 lineage 库。
- shop  → `shop_lineage` 库
- olist → `olist_lineage` 库
支持 `--project shop|olist` 参数。数据按库物理隔离，Job 名无需前缀。

### refresh_lineage_html.py

读取 `lineage_data_{project}.json`, 注入到对应 HTML 中刷新血缘可视化页面。
支持 `--project shop|olist` 参数。

shop 项目: 输出到 `lineage/lineage.html` 和 `lineage/lineage_job.html`
olist 项目: 输出到 `olist/lineage.html` 和 `olist/lineage_job.html`

### lineage DDL

`lineage/ddl/` 下定义了 lineage 数据库的 7 张表: `datasource`, `table_info`, `column_info`, `job`, `column_lineage`, `indirect_lineage`, `table_lineage`。

## 分区策略

所有表按以下规则引入 RANGE 分区：

| 层 | 分区列 | 说明 |
|----|--------|------|
| ODS | `create_time` | 全量刷新，按源系统创建时间分区 |
| DWD 维度 | `snapshot_date` | 每日快照，追加模式，UNIQUE KEY 含 `snapshot_date`，`etl_time` 为纯加工时间戳 |
| DWD 事实 | `order_date` | 全量刷新，按业务日期分区 |
| DWS 日表 | `stat_date` | 全量刷新，按统计日期分区 |
| DWS 月表 | `stat_month_date` | 仅刷新当月分区，DELETE + INSERT |
| ADS 日表 | `stat_date` | 全量刷新，按统计日期分区 |
| ADS 月表 | `stat_month_date` | 仅刷新当月分区，DELETE + INSERT |

分区保留窗口: 7 天 + 1 个 `p_future` 分区。

## ETL 参数

支持 `@etl_date` 变量，用于重跑历史数据：

| 目标表 | 参数用法 | `snapshot_date` |
|--------|----------|-----------------|
| dwd_customer / dwd_product / dwd_store | `CAST(@etl_date AS DATE)` | 按 `@etl_date` 生成 |
| dws_category_sales_monthly / ads_store_performance | `DATE_FORMAT(@etl_date, '%Y-%m')` | 按 `@etl_date` 所在月处理 |

默认值 `CURDATE()`，不传参时按今天跑。

调用方式：
```bash
# 默认（当天）
mysql -h172.16.0.90 -P9030 -uroot < shop/tasks/dwd_customer.sql

# 重跑历史某天
mysql -h172.16.0.90 -P9030 -uroot \
  -e "SET @etl_date = '2025-01-01'; source shop/tasks/dwd_customer.sql;"

# 批量重跑（3 天维度快照 + 3 个月度）
for d in 2025-01-01 2025-01-02 2025-01-03; do
  for t in dwd_customer dwd_product dwd_store; do
    mysql -h172.16.0.90 -P9030 -uroot \
      -e "SET @etl_date = '$d'; source shop/tasks/${t}.sql;"
  done
done
```

## 分支策略

- 每次 DDL 或 ETL 变更必须在新分支上开发
- 分支命名: `feat/<描述>` 或 `refactor/<描述>`
- 完成后合并回主干并推送 GitHub

## Git Commit 规范

参见 [commit_message.md](./commit_message.md)。
