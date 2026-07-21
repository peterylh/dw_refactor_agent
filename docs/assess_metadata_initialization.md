# Assess 元数据初始化与刷新

本文说明 `assess` 相关元数据的初始化顺序、工具职责和常用命令。项目级元数据主要分两类：

- `warehouses/{project}/business_taxonomy.yaml`: 人工维护的数据域、业务板块和项目上下文。
- `warehouses/{project}/business_processes.yaml`: LLM 发现并经人工确认的业务过程。
- `warehouses/{project}/semantic_subjects.yaml`: LLM 发现并经人工确认的语义主题。
- `warehouses/{project}/mid/models/{table_name}.yaml`: DIM/DWD/DWS 表级模型元数据，维护 layer、table_type、业务语义引用、entities、grain、metrics 和执行策略。
- `warehouses/{project}/ads/models/{table_name}.yaml`: ADS 表级模型元数据。
- `warehouses/{project}/ods/models/{catalog}/{database}/{table_name}.yaml`: ODS 表级模型元数据。

推荐把这些文件作为项目资产放在 Git 中维护。工具直接写工作区，使用 `git diff` / `git add -p` 审查和接受变更。

## 推荐初始化流程

### 1. 先准备血缘数据

表级 LLM 巡检和目录发现会使用 DDL、任务 SQL、上下游、字段血缘和已有模型元数据。

```bash
python -m dw_refactor_agent.lineage.lineage_extractor --project shop
```

默认输出到 `warehouses/{project}/artifacts/lineage/lineage_data.json`。

### 2. 初始化或更新业务语义目录

无 LLM 的初始化只创建目录骨架，并仅从已有 `business_taxonomy.yaml` 保留数据域、业务板块字典；不会再从 `naming_config.yaml` 合并这些主数据，也不会再根据表名硬猜业务过程。

如果项目目录仍有旧版 `business_semantics.yaml`，初始化会把它作为迁移来源，并在非 dry-run 写入完成后删除旧文件。partial-split
场景下只回填缺失的拆分文件；已存在的 `business_taxonomy.yaml` 为准，旧文件中的 taxonomy 段和 `project_context` 不会覆盖或合并进去。

```bash
python -m dw_refactor_agent.assessment.business_semantics_catalog --project shop --dry-run
python -m dw_refactor_agent.assessment.business_semantics_catalog --project shop
```

使用 LLM 时，工具会先做表级巡检，再从巡检结果聚类生成 catalog：

```bash
python -m dw_refactor_agent.assessment.business_semantics_catalog --project shop --llm --dry-run --overwrite
python -m dw_refactor_agent.assessment.business_semantics_catalog --project shop --llm --overwrite
```

LLM 发现的原则：

- fact 表从指标字段的 `business_process` 归并到 `business_processes`。
- dimension 表从 primary entity 归并到 `semantic_subjects`。
- 数据域/业务板块只从人工维护的 taxonomy 读取；未命中时不写入人工主数据。
- 不把维度主题、实体管理、运营管理类表强行写成业务过程。
- 表级归属会写入模型 YAML；catalog 不长期维护 `tables`。

### 3. 人工修订 catalog

检查并修订：

- `business_taxonomy.yaml` 中的 `data_domains`: 数据域，通常数量较少，可以由用户稳定维护。
- `business_taxonomy.yaml` 中的 `business_areas`: 业务板块。
- `business_processes.yaml` 中的 `business_processes`: 严格业务过程，应对应可度量事件、活动或汇总事实。
- `semantic_subjects.yaml` 中的 `semantic_subjects`: 维度/实体属性表的语义主题，通常对应维表主实体。

不要在 catalog 中长期维护 `tables`。表到业务过程/语义主题的归属以
模型 YAML 为准；catalog 只维护 code、名称、归属域、别名、说明等治理信息。

### 4. 从 catalog 刷新 models

```bash
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --mode refresh --dry-run
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --mode refresh
```

这个命令不调用 LLM。它读取项目业务语义目录三份 YAML、
`warehouses/{project}/ods/models/{catalog}/{database}/*.yaml`、`warehouses/{project}/mid/models/*.yaml`
和 `warehouses/{project}/ads/models/*.yaml`，以 models 中已有的 `business_process` /
`semantic_subject` 为表级归属事实，再从 catalog 补齐这些 code 对应的数据域和业务板块。

写入内容包括：

- 对缺失的 model 文件创建基础 YAML。
- 写入或刷新 `version`、`name`、`layer`、`table_type`、`execution.materialized`。
- 对 DWD 写入 `data_domain`。
- 对 DWD/DWS 写入 `business_area`。
- 对 fact 表保留 catalog 中存在的已有 `business_process`，并清理 stale code。
- 对 dimension 表保留 catalog 中存在的已有 `semantic_subject`，并移除不适用或 stale 的 `business_process`。
- 清理 stale `business_process` / `semantic_subject` 时，保留仍在 taxonomy 中的已有 `data_domain` / `business_area`。
- 对还没有 `business_process` / `semantic_subject` 归属的模型，保留仍在 taxonomy 中的已有 `data_domain` / `business_area`。

它不会识别指标，不会重算 entities/grain，不会根据 catalog 反向给表分配业务过程，也不会改 DDL、任务 SQL、表名或文件名。

如果某张表的 model 中还没有 `business_process` 或 `semantic_subject`，工具仍会为该表创建或保留基础 model 元数据，但不会凭表名生成业务过程。

### 5. 冷启动生成 models

冷启动入口统一使用 `--mode generate`。执行前不需要手工创建三份 split catalog YAML：如果缺少
`business_taxonomy.yaml`、`business_processes.yaml` 或 `semantic_subjects.yaml`，`generate` 会自动补齐目录骨架。

```bash
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --mode generate --dry-run
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --mode generate --llm --dry-run
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --mode generate
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --mode generate --llm --require-complete
```

`generate --dry-run` 不写 catalog、不写 model 文件、不删除旧 models；结果 JSON 会通过
`planned_catalog_written_names` 和 `planned_deleted_model_files` 报告计划写入或删除的文件，并使用内存中的 catalog skeleton 继续模拟生成。
加 `--llm` 时，dry-run 会基于内存中的冷启动基础 models 构建巡检上下文，不读取当前磁盘上的旧 model 作为分层先验。
正式执行会先在内存中生成完整候选并运行发布校验。执行配置从 task SQL 确定性推导：
对目标表执行 `TRUNCATE TABLE` 对应 `full/replace_all`，按 ETL 参数删除目标切片的任务对应
`incremental`，并从目标表 DELETE 条件提取 `execution.slice`；存在 full-refresh
伴随任务时使用 `companion`，否则使用 `replay_slices`。

LLM 结果先经过 typed recovery 和 section-aware decision。单表业务语义、实体/grain 或指标
不完整时，只隔离受影响 section；默认仍发布完整的 v3 managed model set，状态为
`published_with_quarantine`。正式 model 中被隔离 section 的字段会被删除，详细候选只保留在
结果 JSON/checkpoint。例如未执行 LLM 的 MID model 只保留确定性字段：

```yaml
version: 3
name: dwd_order_detail
operational_layer: DWD
execution:
  materialized: full
  full_refresh_strategy: replace_all
governance:
  schema_version: 1
  status: quarantined
  withheld_sections:
    - classification
    - business_semantics
    - entities
    - grain
    - metrics
  reasons:
    classification: [inspection_not_requested]
    business_semantics: [inspection_not_requested]
    entities: [inspection_not_requested]
    grain: [inspection_not_requested]
    metrics: [inspection_not_requested]
```

未确认的 business process/semantic subject 只写 proposal audit，不会进入三份正式 catalog；
用户确认 catalog 后再次运行，相关 section 才可能激活。`--require-complete` 要求所有适用
section 都 active；存在 quarantine 时返回 `not_published_incomplete` 且正式文件完全不变。

无法解析的执行契约、未知 issue/schema、资产 manifest 变化等确定性错误仍返回 `blocked`；
项目级 API/解析故障触发巡检 breaker，返回 `not_published_inspection_failure`。DWD/DWS 没有
task SQL 等确定性合同错误也不会用 quarantine 掩盖。generate 的巡检资产角色只从 DDL/task
和内存候选构建，不扫描旧 model YAML；confirmed catalog 与完整 models 文件集先全部暂存，
再在项目 publication lock 下通过 journal 事务发布，普通异常会回滚整组文件。

`publication` 的主要状态和 CLI 退出码如下：

| 状态 | 正式写入 | 退出码 |
| --- | --- | --- |
| `published` / `published_with_quarantine` | 是 | 0 |
| `blocked` | 否 | 1 |
| `not_published_incomplete` / `not_published_inspection_failure` | 否 | 2 |
| 正式文件已发布但 `finalization_status=failed` | 已发布 | 3 |

`--dry-run` 的 `status` 固定为 `dry_run`，但 `candidate_status`、`complete` 和
`would_publish_status` 仍反映真实 gate；因此 strict dry-run 发现 quarantine 时退出码也是 2，
且不会写 catalog、models 或删除旧文件。

非 dry-run 的 `generate --llm` 会为长时间运行自动创建逐表检查点：

```text
warehouses/{project}/
├── mid/
└── mid_checkpoints/
    ├── manifest.json
    ├── llm_layer_classification.csv
    └── {table_name}.{context_hash}.inspection.json
```

每张 MID 表巡检完成后会立即写入对应的巡检 sidecar 和 manifest 状态，不再生成逐表
检查点 YAML。所有表巡检完成后、进入 catalog 合并和项目级发布校验前，流程会一次性
生成 `llm_layer_classification.csv`；因此后续候选构建或发布校验失败时，CSV 仍会保留。
CSV 每张成功表一行，只包含最终 `status=passed` 的 LLM 巡检结果，列出
`table_name`、`declared_layer`、`inferred_layer`、`table_type`、`confidence` 和
`inspection_status`。若表巡检阶段本身尚未全部完成就中断，则不会生成不完整 CSV。
正常发布后，正式 `mid/models/*.yaml` 是最终权威结果。

检查点同时为每个实际 prompt 上下文保存完整巡检结果 sidecar 和内容哈希。下一次使用相同
项目执行 `generate --llm` 时，会先校验上一轮 manifest、sidecar 内容哈希和当前 prompt
上下文哈希；只有当前 cache/checkpoint policy 允许且无损的结果才能恢复，并且恢复后仍会
重新执行当前 recovery、decision、proposal、依赖级联和 governance 合同，不能直接把旧的
effective model 当作本轮正式候选。因重试请求异常而临时回退到旧结果的单表结果不会进入恢复集。初检与注入上游指标后的
复检使用不同上下文哈希，可分别恢复；上一轮 `blocked`、缺失、损坏或输入已经变化的表会重新
巡检。因此项目级发布失败后，保持输入不变重跑时只消耗失败表或失效上下文的 API 调用。
如果结果在原始 LLM 返回后、generate 分层解析阶段才变为 `blocked`，manifest 会记录该上下文
哈希的失效标记；下一轮会先从普通 `inspect.json` 中持久删除同哈希 variant，并在当前运行中
继续绕过该缓存。这样即使后续清理旧失效标记，已经被 generate 拒绝的普通缓存也不会重新
生效。提高 `--max-retries` 不会使已经成功的检查点失效。

`--no-cache` 会同时禁用普通巡检缓存和跨轮检查点恢复，强制全量重新调用。新运行开始时会
清理旧的分层 CSV、legacy 检查点 YAML、失败结果和孤立 sidecar，但保留已经校验通过的结果 sidecar 作为恢复源；
新 manifest 会记录 `resumed_from_run_id`、恢复候选数和实际恢复数。同一项目只允许一个检查点
生成流程运行，重叠运行会立即失败。巡检 sidecar 和 manifest 通过带内容哈希的待写 journal
协调，中断时会明确保留待恢复状态。巡检期间的检查点写入错误会终止本次生成；
若正式 models 已经原子发布，仅最终 manifest 收尾失败时，命令结果仍保留发布成功状态，并将
检查点标记为 `finalization_failed`。开启默认进度输出时会显示检查点命中；`--quiet` 可关闭。

只想维护业务语义目录时，使用独立入口：

```bash
python -m dw_refactor_agent.assessment.business_semantics_catalog --project shop --dry-run
python -m dw_refactor_agent.assessment.business_semantics_catalog --project shop
```

### 6. 用 LLM 补全模型细节

表级 LLM 巡检用于补全和刷新更细的模型信息：

```bash
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --mode refresh --llm --dry-run
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --mode refresh --llm
```

`refresh --llm` 固定刷新表信息、指标、entities/grain 等全部模型字段；不再从 CLI 暴露
`--write-scope`。新的低质量结果不会删除已有且仍有效的 active section；已有 quarantine 只有
在本轮结果被接受且 confirmed catalog/确定性合同闭合后才激活，并清理对应 reason。可使用
`--require-complete` 拒绝仍含 quarantine 的 refresh 候选。冷启动时也可以使用
`--mode generate --llm`，先生成基础 models，再补全 LLM 元数据。

## 常见问题

### `--mode refresh` 是什么？

它是 catalog 与 models 的确定性对齐命令。默认不做语义识别，也不调用 DeepSeek；前提是 catalog 已经由 LLM 或人工确认过，models 中的表级归属也已经存在或由 LLM 发现阶段写入。

典型用途：

- catalog 已经修订完，需要根据 models 里的 `business_process` / `semantic_subject` 补齐 `data_domain` / `business_area`。
- 新项目还没有模型 YAML，需要先用 `--mode generate` 按 DDL 和 catalog 创建基础 model 文件。
- catalog 的 process/subject 所属域或板块调整后，需要刷新 models 中的业务语义字段。

### 已存在业务语义目录时会怎样？

业务语义目录默认不会覆盖。需要更新时在 `assessment.business_semantics_catalog` 使用 `--overwrite`，并通过 Git diff 审查结果。`model_metadata_writer --mode generate` 只会自动补齐缺失的 split catalog 文件。

### naming_config.yaml 和 catalog 的字典是什么关系？

`naming_config.yaml` 不再维护 `data_domains` 和 `business_areas` 的主数据。项目 `business_taxonomy.yaml` 中的 `data_domains` / `business_areas` 会合并进命名配置，供命名校验读取。

### 目录发现和模型刷新为什么分两步？

catalog 是治理层，应该先由 LLM 初始化，再人工修订确认。models 是执行和评估层，应该使用确认后的 catalog 进行刷新。分两步可以让 Git diff 更清晰，也避免 LLM 每次刷新 models 时生成一套不稳定的业务过程编码。

## 常用检查命令

```bash
python -m dw_refactor_agent.assessment.assess_middle_layer --project shop --model-design
python -m dw_refactor_agent.assessment.assess_middle_layer --project shop
make test
```
