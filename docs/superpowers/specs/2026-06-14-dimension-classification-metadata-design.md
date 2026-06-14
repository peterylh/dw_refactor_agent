# Dimension Classification Metadata Design

## Goal

识别 DIM 表的两条分类轴，并把结果写入 `models/*.yaml`，供命名规范检查判断维表名称是否准确。

## Metadata

新增两个 DIM 专用模型字段：

- `dimension_role`: `BASE` 或 `ADDT`，表示主维度或辅维度。
- `dimension_content_type`: `INFO`、`TAG` 或 `TREE`，表示属性信息、标签或树形层级。

`semantic_subject` 与 `entities[type=primary].code` 继续表示 DIM 主实体。DIM 表应满足：

```text
semantic_subject == entities[type=primary].code
```

## Naming Mapping

命名配置中的 DIM 段改为更清晰的术语：

```text
DIM_ROLE             <-> models.dimension_role
MODEL_ENTITY         <-> models.entities[type=primary].code
DIM_DESC             <-> 表名描述段
DIM_CONTENT_TYPE     <-> models.dimension_content_type
```

`DIM_BASE_CUST_INFO` 表示 `dimension_role=BASE`、主实体 `CUST`、内容形态 `INFO`。

## Flow

`assess/llm/table_inspector.py` 的 prompt 要求 LLM 返回 `dimension_role` 与 `dimension_content_type`。解析层只接受枚举值，非法值归空。

`assess/llm/model_metadata_writer.py` 在 DIM 表回写时写入这两个字段。非 DIM 表不写入 DIM 分类字段。

`assess/scoring/naming.py` 在 DIM 表命名模板通过后，解析表名中的 `DIM_ROLE` 与 `DIM_CONTENT_TYPE`，分别与 model 元数据对齐。缺失或不一致都输出命名问题。

## Tests

新增测试覆盖：

- prompt 包含 DIM 分类要求和 JSON schema 字段。
- LLM 响应解析、缓存和报告保留两个字段。
- DIM 模型回写两个字段。
- naming config 能解析 `DIM_ROLE` 和 `DIM_CONTENT_TYPE`。
- naming scorer 能发现 DIM 表名角色/内容形态与 model 不一致。
