# Refactor 目录级 AGENTS 文档拆分设计

## 目标

为 `src/dw_refactor_agent/refactor/` 新增标准大写的 `AGENTS.md`，集中说明 refactor 工具、标准工作流、关键运行语义和输出物；同时精简项目根 `AGENTS.md`，使其只保留模块摘要、入口命令和目录文档链接。

## 文档边界

- 根 `AGENTS.md` 负责项目级导航，不重复维护 refactor 的参数、阶段细节和输出字段。
- `src/dw_refactor_agent/refactor/AGENTS.md` 负责 refactor 模块的开发与使用约束。
- `docs/refactor_guides/` 继续负责表/字段重命名等数仓资产操作指南，不并入模块级 AGENTS 文档。

## 目录级文档结构

新文档包含：

1. 适用范围，以及修改 refactor 代码或 refactor run 产物逻辑前应阅读本文件的约束。
2. `run.py`、`session.py`、增量血缘与变更分析、issue diff、verification plan、shadow manifest/rewrite/run、compare 的职责地图。
3. `start → analyze → shadow-run → compare` 标准流程、常用命令及分区要求。
4. `warehouses/{project}/artifacts/refactor_runs/{run_id}/` 输出目录树。
5. 各类输出物的生产阶段、语义、生命周期和下游消费者，明确冻结基线与可再生产物的区别。
6. 最小重算、生产读穿、QA 写入、分区执行、验证锚点和行比较排除列等关键约束。
7. 修改后的针对性检查建议，并遵循项目统一的 conda/Makefile 测试规则。

## 根文档调整

删除现有 refactor 长章节，替换为简短摘要：

- 工具用途与支持项目。
- 修改前阅读目录级 `AGENTS.md` 的链接。
- 四阶段工作流的一行入口命令。
- refactor run 的产物根路径和简要目录含义。
- schema identity 变更后需重建基线的提醒。

## 验证

- 检查两份 Markdown 的标题层级、相对链接和命令路径。
- 搜索根文档，确认详细参数和输出字段已下沉且没有形成互相矛盾的重复说明。
- 对照 refactor 源码中的 CLI、session 路径和 plan/manifest 写入逻辑，确认文档描述与当前实现一致。

