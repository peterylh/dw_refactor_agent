---
name: reinit-db
description: |
  清空 shop_dm/olist_dm 所有表数据 → 重灌 ODS → 按 DAG 拓扑重算全层。
  适用于开发环境首次部署初始化、数据紊乱重建、回归验证基线数据等场景。触发词：初始化数据库、重置数据、重建数仓、reinit。
---

# 初始化数据库 (reinit-db)

清空 shop_dm 所有表数据 → 重灌 ODS → 按 DAG 拓扑重算全层。

## 使用场景

- 开发环境首次部署后初始化数据
- 数据紊乱需要从头重建
- 回归验证基线数据

## 默认行为

默认初始化 **2025-01-01 ~ 2025-01-03** 三天数据。

## 执行

```bash
PYTHONPATH=src python -m dw_refactor_agent.execution.reinit_project --project shop --etl-dates 2025-01-01 2025-01-02 2025-01-03
```

## 自定义日期

```bash
# 单日
PYTHONPATH=src python -m dw_refactor_agent.execution.reinit_project --project shop --etl-dates 2025-01-01

# 自动发现（从 ODS 表 create_time 推导）
PYTHONPATH=src python -m dw_refactor_agent.execution.reinit_project --project shop
```

## 流程说明

1. **清空**: 按 ads → dws → dwd → ods 顺序 TRUNCATE 所有表
2. **ODS 初始化**: 执行 `warehouses/shop/ods/data/internal/shop_dm/ods_*.sql` 灌入 ODS 层
3. **ETL 日期确定**: 按传入的 `--etl-dates` 或自动从 ODS 发现
4. **作业执行**: 调用 `src/dw_refactor_agent/execution/task_run.py` 按 DAG 拓扑依次执行 DWD → DWS → ADS

## 相关文件

| 文件 | 说明 |
|------|------|
| `src/dw_refactor_agent/execution/reinit_project.py` | 主入口，清空 + 初始化 + 调度 |
| `src/dw_refactor_agent/execution/task_run.py` | DAG 拓扑执行器 |
| `warehouses/shop/ods/data/internal/shop_dm/` | ODS 层初始化 SQL |
| `warehouses/shop/{mid,ads}/tasks/` | ETL 加工作业 SQL |
