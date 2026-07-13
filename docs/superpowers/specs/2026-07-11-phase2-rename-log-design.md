# Phase 2 RENAME 日志修复设计

## 背景

shadow-run 实际执行 Phase 2 DDL 变更成功后，统一从 `table_name` 读取展示名。
`RENAME` 变更使用 `old_name` 和 `new_name`，没有 `table_name`，因此日志显示为
`[RENAME] ?`。dry-run 已有 `old_name` 回退，但只显示旧表名，且与实际执行使用
不同的展示逻辑。

## 目标

- 实际执行和 dry-run 对同一 DDL 变更输出一致的名称。
- `RENAME` 同时展示旧表名和新表名：`old_name -> new_name`。
- `CREATE`、`ALTER`、`DROP` 等现有 `table_name` 日志保持不变。
- 字段缺失时安全降级为现有的 `?`，不影响 DDL 执行和结果 JSON。

## 设计

在 `shadow_run.py` 增加一个无副作用的 DDL 展示名辅助函数：

1. 当 `change_type` 大小写不敏感地等于 `RENAME`，且旧、新名称都存在时，返回
   `"{old_name} -> {new_name}"`。
2. 否则优先返回 `table_name`。
3. `RENAME` 信息不完整时依次回退到存在的 `old_name` 或 `new_name`。
4. 所有候选字段均缺失时返回 `?`。

实际执行成功日志和 dry-run 预览都调用该函数。失败日志保留当前异常信息格式，避免
扩大本次修复范围；失败详情仍可由 SQL 和结果 JSON 定位。

## 测试与验证

按 TDD 增加回归测试，先证明当前实际执行输出 `[RENAME] ?`：

- 构造 Shop RENAME plan，mock 数据库执行边界，运行非 dry-run shadow plan。
- 断言日志包含完整的
  `[RENAME] shop_dm_qa.dwd_inventory -> shop_dm_qa.M_SHOP_05_INV_DF`。
- 断言日志不包含 `[RENAME] ?`。
- 同步断言 dry-run 使用相同展示格式。
- 覆盖普通 `ALTER` 的 `table_name` 输出和缺字段降级，防止改变其他 DDL 行为。

自动化验证通过后，使用 Shop 数据集市生成或复用一个表重命名验证计划，执行真实
shadow-run，并从完整日志中确认 Phase 2 不再出现 `[RENAME] ?`。真实验证仅操作 QA
库；生产库作为读取源，不修改生产资产。

## 非目标

- 不修改 verification plan 或 shadow-run result 的 JSON schema。
- 不调整 DDL 推导、SQL 重写、执行顺序或 compare 行为。
- 不清理生产库中的历史实验表。
