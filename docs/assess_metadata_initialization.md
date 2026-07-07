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
- 写入或刷新 `version`、`name`、`layer`、`table_type`、`config.materialized`。
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
```

`generate --dry-run` 不写 catalog、不写 model 文件、不删除旧 models；结果 JSON 会通过
`planned_catalog_written_names` 和 `planned_deleted_model_files` 报告计划写入或删除的文件，并使用内存中的 catalog skeleton 继续模拟生成。
加 `--llm` 时，dry-run 会基于内存中的冷启动基础 models 构建巡检上下文，不读取当前磁盘上的旧 model 作为分层先验。
正式执行时会先替换当前项目 models，再根据 DDL、catalog 与表名生成基础模型 YAML。

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
`--write-scope`。冷启动时也可以使用 `--mode generate --llm`，先生成基础 models，再补全 LLM 元数据。

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
