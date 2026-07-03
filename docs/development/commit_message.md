# Git Commit Message Convention

遵循 [Conventional Commits](https://www.conventionalcommits.org/) 规范，格式如下：

```
<type>(<scope>): <subject>
```

## Type

| Type       | 说明                                                                 |
|------------|----------------------------------------------------------------------|
| `feat`     | 新功能                                                               |
| `fix`      | 修复 Bug                                                             |
| `docs`     | 仅文档变更                                                           |
| `style`    | 代码格式调整（空格、格式化、缺少分号等），不影响代码逻辑                |
| `refactor` | 重构（既不修复 Bug 也不添加新功能的代码变更）                          |
| `perf`     | 性能优化                                                             |
| `test`     | 添加或修改测试                                                       |
| `chore`    | 构建过程或辅助工具的变更（如修改配置文件、依赖等）                      |
| `revert`   | 回滚提交                                                             |

## Scope（可选）

本次提交影响的范围，如模块名、文件名等。例如：`feat(dwd):`、`fix(lineage):`。

## Subject

- 使用 **中文** 或 **英文** 描述，团队统一即可
- 首字母 **小写**，结尾 **不加句号**
- 祈使句，说明 **做了什么**，而不是 **做了什么**的过去式
  - ✅ `feat: add store sales aggregation`
  - ❌ `feat: added store sales aggregation`
- 不超过 **72 个字符**

## Body（可选）

- 如果 `subject` 不足以说明，在空行后补充详细描述
- 说明 **为什么做这个变更** 以及 **如何做的**
- 每行不超过 72 个字符

## Footer（可选）

- 关联 Issue：`Closes #123`, `Fixes #456`
- BREAKING CHANGE：`BREAKING CHANGE: <description>`

## 示例

```
feat(dwd): add store daily sales aggregation table

- Join ods_order and ods_store to build dwd_store_sales_daily
- Include store_id, date, total_amount, order_count

Closes #42
```

```
fix(lineage): handle subquery alias in column lineage

Subquery alias was not resolved correctly when extracting column-level lineage,
causing missing upstream columns for CTE-based ETL.

Fixes #18
```

```
docs: add commit message convention guide
```

```
refactor(extractor): split lineage extraction into modular pipeline
```

```
chore: add ruff config for python linting
```
