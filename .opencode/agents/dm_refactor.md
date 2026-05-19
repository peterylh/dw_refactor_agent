# DM Refactor Agent

执行数仓重构全流程：建分支 → 修改 DDL/Task → 语法验证 → 验证库数据校验 → 生成总结报告。

## 用法

当用户提出重构需求（修改表结构、调整 ETL 逻辑、新增/删除字段等）时，调用此 Agent。

## 工作流

### 步骤 1：创建重构分支

```bash
git checkout -b refactor/<描述>
```

### 步骤 2：修改 DDL 和 Task

依据用户需求修改对应文件：
- DDL: `shop/ddl/*.sql` 或 `olist/ddl/*.sql`
- ETL: `shop/tasks/*.sql` 或 `olist/tasks/*.sql`

修改时需：
- 利用 `lineage/` 工具及代码库追踪上下游依赖
- 字段变更须同步修改所有下游 SELECT / JOIN 逻辑
- 确保 DDL 与 ETL 的列数、列名一致
- 可选：调用 `code_reviewer` agent 辅助审查变更

### 步骤 3：测试环境语法验证

在 Doris 测试环境执行：

1. **重建涉及的表** — 执行修改后的 DDL (`DROP + CREATE`)
2. **运行修改的 ETL 作业** — 确保 SQL 执行无语法错误

### 步骤 4：验证库数据校验

使用 `refact/` 工具链进行系统性验证：

```bash
# 分析变更 → 元数据
python refact/analyze_refact.py [--project shop|olist]

# 执行验证 (自动重置 shop_dm_qa + 基线建表 + DDL + 表映射执行)
python refact/verify_run.py --metadata refact/refact_metadata.json

# 校验对比
python refact/verify_check.py --metadata refact/refact_metadata.json --method all
```

若校验失败，根据失败信息修复代码后重新执行步骤 3-4。

### 步骤 5：生成总结报告

输出 JSON 格式报告到 stdout：

```json
{
  "report_id": "refactor_20260519_143022",
  "timestamp": "2026-05-19T14:30:22+08:00",
  "branch": "refactor/xxx",
  "project": "shop",
  "steps": [
    {
      "step": 1,
      "name": "创建分支",
      "status": "PASS",
      "details": "分支 refactor/xxx 已创建"
    },
    {
      "step": 2,
      "name": "修改 DDL/Task",
      "status": "PASS",
      "details": {
        "files_changed": ["shop/ddl/dwd_xxx.sql", "shop/tasks/dwd_xxx.sql"],
        "change_summary": "xxx 字段类型从 VARCHAR(50) 改为 VARCHAR(100)"
      }
    },
    {
      "step": 3,
      "name": "语法验证",
      "status": "PASS",
      "details": "DDL 建表成功，ETL 作业执行无报错"
    },
    {
      "step": 4,
      "name": "数据校验",
      "status": "PASS",
      "details": {
        "analyze": "检测到 x 个 DDL 变更, x 个作业变更, x 个下游表",
        "verify_run": "三阶段执行完成 (基线建表 / DDL 应用 / 作业执行)",
        "verify_check": "count: PASS, row_compare: PASS"
      }
    }
  ],
  "summary": {
    "overall_status": "PASS",
    "recommendation": "重构和验证已全部完成，请手工操作合并分支并在生产环境上线。"
  },
  "production_notes": {
    "ddl_deploy": "<根据 analyze_refact.py 输出的元数据 (ddl_changes) 提取需要执行的 DDL 表及变更语句>",
    "data_replay": "<根据 analyze_refact.py 输出的元数据 (jobs_to_run) 提取并按序列出需要重算的作业>",
    "rollback": "回滚方式：还原 DDL + 使用上一版本 ETL 重算"
  }
}
```

## 依赖

- Python 3 + sqlglot
- Doris 测试环境连接
- `refact/` 工具链 (`analyze_refact.py`, `verify_run.py`, `verify_check.py`)
- 可选：`code_reviewer` agent, `lineage_qa` agent
