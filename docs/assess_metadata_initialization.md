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

等价入口也可以使用：

```bash
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --catalog-from-llm --dry-run --overwrite-catalog
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --catalog-from-llm --overwrite-catalog
```

### 3. 人工修订 catalog

检查并修订：

- `business_taxonomy.yaml` 中的 `data_domains`: 数据域，通常数量较少，可以由用户稳定维护。
- `business_taxonomy.yaml` 中的 `business_areas`: 业务板块。
- `business_processes.yaml` 中的 `business_processes`: 严格业务过程，应对应可度量事件、活动或汇总事实。
- `semantic_subjects.yaml` 中的 `semantic_subjects`: 维度/实体属性表的语义主题，通常对应维表主实体。

不要在 catalog 中长期维护 `tables`。表到业务过程/语义主题的归属以
模型 YAML 为准；catalog 只维护 code、名称、归属域、别名、说明等治理信息。

### 4. 从 catalog 初始化或刷新 models

```bash
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --from-catalog --write-scope business --dry-run
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --from-catalog --write-scope business
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

### 5. 用 LLM 补全模型细节

表级 LLM 巡检用于补全和刷新更细的模型信息：

```bash
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --dry-run
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop
```

常用写入范围：

```bash
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --write-scope table
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --write-scope metrics
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --write-scope grain
python -m dw_refactor_agent.assessment.llm.model_metadata_writer --project shop --write-scope all
```

说明：

- `table`: 回写 layer/table_type 及适用的业务域/板块。
- `metrics`: 回写 atomic/derived/calculated 指标分组。
- `grain`: 回写 entities/grain。
- `all`: 同时回写上述内容。
- `business`: 仅用于 `--from-catalog`，表示按 models 中已有业务 code 从 catalog 补齐治理信息，并刷新基础表元数据。

## 常见问题

### `--from-catalog --write-scope business` 是什么？

它是 catalog 与 models 的确定性对齐命令。它不做语义识别，也不调用 DeepSeek；前提是 catalog 已经由 LLM 或人工确认过，models 中的表级归属也已经存在或由 LLM 发现阶段写入。

典型用途：

- catalog 已经修订完，需要根据 models 里的 `business_process` / `semantic_subject` 补齐 `data_domain` / `business_area`。
- 新项目还没有模型 YAML，需要先按 DDL 和 catalog 创建基础 model 文件。
- catalog 的 process/subject 所属域或板块调整后，需要刷新 models 中的业务语义字段。

### 已存在业务语义目录时会怎样？

默认不会覆盖。需要更新时使用 `--overwrite` 或 `--overwrite-catalog`，并通过 Git diff 审查结果。

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
