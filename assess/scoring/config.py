"""Shared scoring constants and rule metadata for assess dimensions."""

from __future__ import annotations

from assess.result_model import (
    SEVERITY_HIGH,
    SEVERITY_LOW,
    SEVERITY_MEDIUM,
    rule_meta,
)

# ============================================================
# 评分配置
# ============================================================

# 中间层深度 → 得分映射
# 深度 2 (DWD+DWS) 为理想, 1 (只有一层) 为欠佳, 0 为无中间层, ≥3 为过长
MIDDLE_DEPTH_SCORE = {2: 100, 1: 50, 0: 0}
MIDDLE_DEPTH_FALLBACK = 30  # depth ≥ 3

# 复用满分的下游引用数 (引用数 ≥ N 即满分)
REUSE_FULL_SCORE_AT = 3

DEFAULT_WEIGHTS = {
    "reuse": 0.18,
    "depth": 0.18,
    "model_design": 0.18,
    "naming": 0.18,
    "asset_completeness": 0.09,
    "metadata_health": 0.09,
    "code_quality": 0.1,
}

# 加权违规率配置: 严重度 → 权重
SEVERITY_WEIGHT = {SEVERITY_HIGH: 3, SEVERITY_MEDIUM: 2, SEVERITY_LOW: 1}
# 每表扣分上限 (cap)，防止单张高频表拖垮整体评分
PER_TABLE_CAP = 3
ATOMIC_METRIC_RULE_NAME = "原子指标命名 {ACTION_VERB}_{MEASURE_NOUN}"
DERIVED_METRIC_RULE_NAME = (
    "派生指标命名 {TIME_PERIOD}_{MODIFIER...}_{ATOMIC_METRIC}"
)
DWS_ENTITY_RULE_NAME = "DWS表名实体包含于grain.entities"
DIM_ENTITY_RULE_NAME = "DIM表名实体等于entities.primary.code"
DIM_CLASSIFICATION_RULE_NAME = "DIM表名分类段与模型元数据一致"
DATA_DOMAIN_LAYERS = {"DWD"}
BUSINESS_AREA_LAYERS = {"DWD", "DWS"}
FILE_RULE_DDL = "DDL文件名与建表表名一致"
FILE_RULE_MODEL_NAME = "Model文件名与模型name一致"
FILE_RULE_TASK_SQL = "Task文件名与产出表一致"
FILE_RULE_TOTAL = "文件命名总计"
ASSET_RULE_DDL_MODEL = "DDL表存在Model"
ASSET_RULE_DDL_TASK = "需执行DDL表存在Task"
ASSET_RULE_MODEL_DDL = "Model存在对应DDL表"
ASSET_RULE_TASK_DDL = "Task产出表存在DDL"
ASSET_RULE_TASK_MODEL = "Task产出表存在Model"
ASSET_RULE_TASK_SINGLE_OUTPUT = "Task有且只有一个产出表"
ASSET_RULE_TABLE_SINGLE_WRITER = "目标表有且只有一个产出Task"
ASSET_RULE_TASK_LINEAGE = "Task血缘目标与实际产出一致"
METADATA_HEALTH_RULES = {
    "METADATA_DIM_HAS_PRIMARY_ENTITY": rule_meta(
        name="entities.primary.code已配置",
        severity=SEVERITY_HIGH,
        title="DIM模型缺少主实体",
        remediation_summary="在模型YAML中补齐entities.primary.code或entity.code",
        strategy="update_model_primary_entity",
        edit_scope=["models"],
    ),
    "METADATA_DIM_SEMANTIC_SUBJECT_MATCHES_PRIMARY": rule_meta(
        name="DIM semantic_subject等于主实体",
        severity=SEVERITY_HIGH,
        title="DIM模型semantic_subject与主实体不一致",
        remediation_summary=(
            "在模型YAML中补齐semantic_subject，"
            "并使其等于entities中type=primary的code"
        ),
        strategy="align_dim_semantic_subject",
        edit_scope=["models"],
    ),
    "METADATA_ENTITY_KEYS_EXIST": rule_meta(
        name="entities.key_columns存在于表字段",
        severity=SEVERITY_HIGH,
        title="实体键字段不存在于表结构",
        remediation_summary="修正entities.key_columns，或补齐DDL中的实体键字段",
        strategy="align_entity_key_columns",
        edit_scope=["models", "ddl"],
    ),
    "METADATA_RELATIONSHIP_FROM_PRIMARY": rule_meta(
        name="entities.relationship.from_entity等于主实体",
        severity=SEVERITY_MEDIUM,
        title="实体关系来源与主实体不一致",
        remediation_summary="修正实体relationship.from_entity为当前模型主实体",
        strategy="update_entity_relationship",
        edit_scope=["models"],
    ),
    "METADATA_ENTITY_NOT_DUPLICATE_PRIMARY": rule_meta(
        name="entities.code不同于主实体",
        severity=SEVERITY_MEDIUM,
        title="关联实体与主实体重复",
        remediation_summary="移除重复实体，或修正关联实体code",
        strategy="deduplicate_model_entities",
        edit_scope=["models"],
    ),
    "METADATA_GRAIN_KEYS_EXIST": rule_meta(
        name="grain.keys存在于表字段",
        severity=SEVERITY_HIGH,
        title="粒度键字段不存在于表结构",
        remediation_summary="修正grain.keys，或补齐DDL中的粒度键字段",
        strategy="align_grain_key_columns",
        edit_scope=["models", "ddl"],
    ),
    "METADATA_GRAIN_ENTITIES_PRESENT": rule_meta(
        name="grain.entities已配置",
        severity=SEVERITY_HIGH,
        title="DWS模型缺少grain.entities",
        remediation_summary="在模型YAML中补齐grain.entities",
        strategy="update_model_grain_entities",
        edit_scope=["models"],
    ),
    "METADATA_GRAIN_ENTITIES_DEFINED": rule_meta(
        name="grain.entities属于当前表entities",
        severity=SEVERITY_MEDIUM,
        title="grain.entities引用了当前表未声明实体",
        remediation_summary="在当前模型entities中补齐实体，或修正grain.entities",
        strategy="update_model_grain_entities",
        edit_scope=["models"],
    ),
    "METADATA_DATA_DOMAIN_VALID": rule_meta(
        name="data_domain配置有效",
        severity=SEVERITY_MEDIUM,
        title="data_domain配置无效",
        remediation_summary="按命名字典修正模型YAML中的data_domain",
        strategy="update_model_business_metadata",
        edit_scope=["models"],
    ),
    "METADATA_BUSINESS_AREA_VALID": rule_meta(
        name="business_area配置有效",
        severity=SEVERITY_MEDIUM,
        title="business_area配置无效",
        remediation_summary="按命名字典修正模型YAML中的business_area",
        strategy="update_model_business_metadata",
        edit_scope=["models"],
    ),
}

ASSET_COMPLETENESS_RULES = {
    "ASSET_DDL_HAS_MODEL": rule_meta(
        name=ASSET_RULE_DDL_MODEL,
        severity=SEVERITY_HIGH,
        title="DDL表缺少Model",
        remediation_summary="为该DDL表补齐models/*.yaml元数据文件",
        strategy="create_missing_model",
        edit_scope=["models"],
    ),
    "ASSET_EXECUTABLE_DDL_HAS_TASK": rule_meta(
        name=ASSET_RULE_DDL_TASK,
        severity=SEVERITY_HIGH,
        title="需执行表缺少产出Task",
        remediation_summary="补齐产出该表的tasks/*.sql，或调整模型物化配置",
        strategy="create_missing_task",
        edit_scope=["tasks", "models"],
    ),
    "ASSET_MODEL_HAS_DDL": rule_meta(
        name=ASSET_RULE_MODEL_DDL,
        severity=SEVERITY_HIGH,
        title="Model缺少对应DDL",
        remediation_summary="补齐对应DDL，或删除/修正无效Model",
        strategy="create_missing_ddl",
        edit_scope=["ddl", "models"],
    ),
    "ASSET_TASK_OUTPUT_HAS_DDL": rule_meta(
        name=ASSET_RULE_TASK_DDL,
        severity=SEVERITY_HIGH,
        title="Task产出表缺少DDL",
        remediation_summary="补齐对应DDL，或修正Task产出目标",
        strategy="create_missing_ddl",
        edit_scope=["ddl", "tasks"],
    ),
    "ASSET_TASK_OUTPUT_HAS_MODEL": rule_meta(
        name=ASSET_RULE_TASK_MODEL,
        severity=SEVERITY_HIGH,
        title="Task产出表缺少Model",
        remediation_summary="补齐对应Model，或修正Task产出目标",
        strategy="create_missing_model",
        edit_scope=["models", "tasks"],
    ),
    "ASSET_TASK_SINGLE_OUTPUT": rule_meta(
        name=ASSET_RULE_TASK_SINGLE_OUTPUT,
        severity=SEVERITY_HIGH,
        title="Task产出表数量不为1",
        remediation_summary="调整Task，使其有且只有一个持久目标表",
        strategy="split_or_fix_task_outputs",
        edit_scope=["tasks"],
    ),
    "ASSET_TABLE_SINGLE_WRITER": rule_meta(
        name=ASSET_RULE_TABLE_SINGLE_WRITER,
        severity=SEVERITY_HIGH,
        title="目标表存在多个产出Task",
        remediation_summary="合并重复产出作业，或调整Task写入目标",
        strategy="deduplicate_table_writers",
        edit_scope=["tasks"],
    ),
    "ASSET_TASK_LINEAGE_MATCHES_OUTPUT": rule_meta(
        name=ASSET_RULE_TASK_LINEAGE,
        severity=SEVERITY_HIGH,
        title="Task血缘目标与实际产出不一致",
        remediation_summary="刷新血缘，或修正Task中的实际写入目标",
        strategy="refresh_or_fix_task_lineage",
        edit_scope=["tasks", "lineage"],
    ),
}

ASSET_RULE_IDS = {
    ASSET_RULE_DDL_MODEL: "ASSET_DDL_HAS_MODEL",
    ASSET_RULE_DDL_TASK: "ASSET_EXECUTABLE_DDL_HAS_TASK",
    ASSET_RULE_MODEL_DDL: "ASSET_MODEL_HAS_DDL",
    ASSET_RULE_TASK_DDL: "ASSET_TASK_OUTPUT_HAS_DDL",
    ASSET_RULE_TASK_MODEL: "ASSET_TASK_OUTPUT_HAS_MODEL",
    ASSET_RULE_TASK_SINGLE_OUTPUT: "ASSET_TASK_SINGLE_OUTPUT",
    ASSET_RULE_TABLE_SINGLE_WRITER: "ASSET_TABLE_SINGLE_WRITER",
    ASSET_RULE_TASK_LINEAGE: "ASSET_TASK_LINEAGE_MATCHES_OUTPUT",
}

REUSABILITY_RULES = {
    "REUSE_DOWNSTREAM_REACHES_TARGET": rule_meta(
        name="中间层表达到目标复用度",
        severity=SEVERITY_LOW,
        title="中间层表复用不足",
        remediation_summary="确认该中间层表是否应保留，或补充下游复用链路",
        strategy="review_reuse_or_downstream_dependencies",
        edit_scope=["tasks", "models"],
    ),
}

LINEAGE_DEPTH_RULES = {
    "DEPTH_MIDDLE_LAYER_IS_OPTIMAL": rule_meta(
        name="ADS链路中间层深度合理",
        severity=SEVERITY_MEDIUM,
        title="ADS链路中间层深度不合理",
        remediation_summary="调整ADS上游链路，使其经过合理的DWD/DWS/DIM中间层",
        strategy="refactor_lineage_depth",
        edit_scope=["tasks", "models"],
    ),
}

ARCHITECTURE_RULES = {
    "ARCH_ALLOWED_DEPENDENCY": rule_meta(
        name="层级依赖方向合理",
        severity=SEVERITY_LOW,
        title="层级依赖方向合理",
        remediation_summary="无需处理",
        strategy="none",
        edit_scope=[],
    ),
    "ARCH_REVERSE_DEPENDENCY": rule_meta(
        name="禁止反向依赖",
        severity=SEVERITY_HIGH,
        title="存在反向依赖",
        remediation_summary="调整作业依赖方向，避免高层数据反向流入低层",
        strategy="refactor_reverse_dependency",
        edit_scope=["tasks"],
    ),
    "ARCH_SAME_LAYER_DEPENDENCY": rule_meta(
        name="避免非必要同层依赖",
        severity=SEVERITY_LOW,
        title="存在同层依赖",
        remediation_summary="确认同层依赖是否必要，必要时沉淀公共上游或调整分层",
        strategy="review_same_layer_dependency",
        edit_scope=["tasks", "models"],
    ),
    "ARCH_SKIP_LAYER_DEPENDENCY": rule_meta(
        name="避免跳层依赖",
        severity=SEVERITY_MEDIUM,
        title="存在跳层依赖",
        remediation_summary="补齐或复用中间层，避免ODS/DWD直接服务高层结果",
        strategy="insert_or_reuse_middle_layer",
        edit_scope=["tasks", "models"],
    ),
    "ARCH_DECLARED_LAYER_MATCHES_LLM": rule_meta(
        name="配置层与LLM推断层一致",
        severity=SEVERITY_MEDIUM,
        title="表层级配置疑似错误",
        remediation_summary="复核模型layer配置，必要时修正models/*.yaml",
        strategy="update_model_layer",
        edit_scope=["models"],
    ),
    "ARCH_DWD_DIMENSION_POSITION": rule_meta(
        name="维度表不应位于DWD",
        severity=SEVERITY_LOW,
        title="维度表位置不当",
        remediation_summary="将维度型表迁移到DIM层，或修正表类型判断",
        strategy="move_dimension_table_to_dim",
        edit_scope=["ddl", "tasks", "models"],
    ),
    "ARCH_TABLE_TYPE_MATCHES_LLM": rule_meta(
        name="配置表类型与LLM推断一致",
        severity=SEVERITY_MEDIUM,
        title="表类型配置疑似错误",
        remediation_summary="复核table_type配置，必要时修正models/*.yaml",
        strategy="update_model_table_type",
        edit_scope=["models"],
    ),
    "ARCH_DATA_DOMAIN_MATCHES_LLM": rule_meta(
        name="数据域配置与LLM推断一致",
        severity=SEVERITY_MEDIUM,
        title="数据域配置疑似错误",
        remediation_summary="复核data_domain配置，必要时修正models/*.yaml",
        strategy="update_model_business_metadata",
        edit_scope=["models"],
    ),
    "ARCH_BUSINESS_AREA_MATCHES_LLM": rule_meta(
        name="业务板块配置与LLM推断一致",
        severity=SEVERITY_MEDIUM,
        title="业务板块配置疑似错误",
        remediation_summary="复核business_area配置，必要时修正models/*.yaml",
        strategy="update_model_business_metadata",
        edit_scope=["models"],
    ),
}

MODEL_DESIGN_RULES = {
    **ARCHITECTURE_RULES,
    "MODEL_DWD_FACT_NO_AGGREGATION": rule_meta(
        name="DWD事实表保持明细粒度",
        severity=SEVERITY_HIGH,
        title="DWD事实表存在聚合逻辑",
        remediation_summary="将聚合逻辑上移到DWS层，或修正模型分层/表类型",
        strategy="move_aggregation_to_dws",
        edit_scope=["tasks", "models"],
    ),
    "MODEL_DWS_GRAIN_PRESENT": rule_meta(
        name="DWS事实表配置grain",
        severity=SEVERITY_MEDIUM,
        title="DWS事实表缺少grain元数据",
        remediation_summary="在models YAML中补齐grain.entities和time_column",
        strategy="update_model_grain",
        edit_scope=["models"],
    ),
    "MODEL_DWS_GRAIN_MATCHES_GROUP_BY": rule_meta(
        name="DWS grain与SQL GROUP BY一致",
        severity=SEVERITY_MEDIUM,
        title="DWS事实表grain与GROUP BY不一致",
        remediation_summary="修正models grain，或调整SQL GROUP BY以匹配声明粒度",
        strategy="align_grain_with_group_by",
        edit_scope=["models", "tasks"],
    ),
    "MODEL_DWD_FACT_HAS_EVENT_KEY": rule_meta(
        name="DWD事实表包含明细事件键",
        severity=SEVERITY_LOW,
        title="DWD事实表缺少明显事件键",
        remediation_summary="补齐事件/流水/明细键，或在模型entities中声明粒度键",
        strategy="declare_or_add_event_key",
        edit_scope=["models", "ddl", "tasks"],
    ),
    "MODEL_DWS_FACT_HAS_AGGREGATION": rule_meta(
        name="DWS事实表包含聚合逻辑",
        severity=SEVERITY_MEDIUM,
        title="DWS事实表缺少聚合逻辑",
        remediation_summary="将该表调整为明细层，或在DWS作业中补齐汇总逻辑",
        strategy="align_dws_aggregation",
        edit_scope=["tasks", "models"],
    ),
    "MODEL_DWS_SELECT_FIELDS_MATCH_GRAIN": rule_meta(
        name="DWS SELECT普通字段符合声明粒度",
        severity=SEVERITY_HIGH,
        title="DWS输出字段存在明细粒度泄漏",
        remediation_summary="移除明细字段，或将字段纳入grain/GROUP BY以调整汇总粒度",
        strategy="align_dws_select_fields_with_grain",
        edit_scope=["tasks", "models"],
    ),
    "MODEL_DIM_NO_METRIC_GROUPS": rule_meta(
        name="DIM模型不配置指标分组",
        severity=SEVERITY_HIGH,
        title="DIM模型包含指标分组",
        remediation_summary="移除DIM模型中的指标分组，或修正表类型/层级",
        strategy="remove_dim_metric_groups",
        edit_scope=["models"],
    ),
    "MODEL_DWD_FACT_NO_DERIVED_METRICS": rule_meta(
        name="DWD事实表不配置派生或计算指标",
        severity=SEVERITY_MEDIUM,
        title="DWD事实表包含派生或计算指标",
        remediation_summary="将派生/计算指标上移到DWS，或修正指标分组",
        strategy="move_non_atomic_metrics_to_dws",
        edit_scope=["models", "tasks"],
    ),
    "MODEL_DWD_FACT_SINGLE_BUSINESS_PROCESS": rule_meta(
        name="DWD事实表单业务过程",
        severity=SEVERITY_HIGH,
        title="DWD事实表包含多个业务过程",
        remediation_summary="拆分DWD事实表，或修正指标字段的business_process归属",
        strategy="split_dwd_fact_by_business_process",
        edit_scope=["models", "ddl", "tasks"],
    ),
    "MODEL_DWD_FACT_HAS_PRIMARY_ENTITY_OR_GRAIN": rule_meta(
        name="DWD事实表声明业务主键或粒度",
        severity=SEVERITY_HIGH,
        title="DWD事实表缺少业务主键或粒度声明",
        remediation_summary=(
            "在models YAML中补齐entities[type=primary].key_columns，"
            "或声明明确的grain键"
        ),
        strategy="declare_dwd_primary_entity_or_grain",
        edit_scope=["models"],
    ),
    "MODEL_DATE_PARTITION_USES_DATA_DT": rule_meta(
        name="日期分区字段使用data_dt",
        severity=SEVERITY_MEDIUM,
        title="日期分区字段未使用data_dt",
        remediation_summary="将日期分区字段统一为data_dt，并同步DDL、Task和Model引用",
        strategy="rename_date_partition_to_data_dt",
        edit_scope=["ddl", "tasks", "models"],
    ),
    "MODEL_DERIVED_METRIC_BASE_ATOMIC": rule_meta(
        name="派生指标引用上游原子指标",
        severity=SEVERITY_HIGH,
        title="派生指标未正确关联原子指标",
        remediation_summary="为派生指标补充 base_metric_table 和 base_metric，并确保其指向上游 atomic_metrics",
        strategy="link_derived_metric_to_atomic_metric",
        edit_scope=["models", "tasks"],
    ),
}

NAMING_RULES = {
    "NAMING_TABLE_TEMPLATE": rule_meta(
        name="表名符合规范模板",
        severity=SEVERITY_MEDIUM,
        title="表名不符合规范模板",
        remediation_summary="按所在层级的表名模板重命名表，并同步DDL、Task和Model引用",
        strategy="rename_table_and_rewrite_references",
        edit_scope=["ddl", "tasks", "models"],
    ),
    "NAMING_TABLE_MAX_LENGTH": rule_meta(
        name="表名长度符合限制",
        severity=SEVERITY_LOW,
        title="表名超过长度限制",
        remediation_summary="缩短表名并同步相关DDL、Task和Model引用",
        strategy="rename_table_and_rewrite_references",
        edit_scope=["ddl", "tasks", "models"],
    ),
    "NAMING_COLUMN_NAME": rule_meta(
        name="列名符合规范",
        severity=SEVERITY_LOW,
        title="字段名不符合规范",
        remediation_summary="按字段命名规则重命名字段，并同步DDL、Task和Model引用",
        strategy="rename_columns_and_rewrite_references",
        edit_scope=["ddl", "tasks", "models"],
    ),
    "NAMING_ATOMIC_METRIC": rule_meta(
        name=ATOMIC_METRIC_RULE_NAME,
        severity=SEVERITY_MEDIUM,
        title="原子指标命名不合规",
        remediation_summary="按原子指标命名规则修正指标名，并同步相关引用",
        strategy="rename_metric_and_rewrite_references",
        edit_scope=["models", "ddl", "tasks"],
    ),
    "NAMING_DERIVED_METRIC": rule_meta(
        name=DERIVED_METRIC_RULE_NAME,
        severity=SEVERITY_MEDIUM,
        title="派生指标命名不合规",
        remediation_summary="按派生指标命名规则修正指标名，并同步相关引用",
        strategy="rename_metric_and_rewrite_references",
        edit_scope=["models", "ddl", "tasks"],
    ),
    "NAMING_DWS_ENTITY_ALIGNMENT": rule_meta(
        name=DWS_ENTITY_RULE_NAME,
        severity=SEVERITY_MEDIUM,
        title="DWS表名实体与grain.entities不一致",
        remediation_summary="修正DWS表名实体段或模型grain.entities",
        strategy="align_dws_name_with_grain_entities",
        edit_scope=["models", "ddl", "tasks"],
    ),
    "NAMING_DIM_ENTITY_ALIGNMENT": rule_meta(
        name=DIM_ENTITY_RULE_NAME,
        severity=SEVERITY_MEDIUM,
        title="DIM表名实体与主实体不一致",
        remediation_summary="修正DIM表名实体段或模型主实体配置",
        strategy="align_dim_name_with_primary_entity",
        edit_scope=["models", "ddl", "tasks"],
    ),
    "NAMING_DIM_CLASSIFICATION_ALIGNMENT": rule_meta(
        name=DIM_CLASSIFICATION_RULE_NAME,
        severity=SEVERITY_MEDIUM,
        title="DIM表名分类段与模型元数据不一致",
        remediation_summary=(
            "修正DIM表名中的角色/内容形态段，"
            "或修正模型dimension_role/dimension_content_type"
        ),
        strategy="align_dim_name_with_classification_metadata",
        edit_scope=["models", "ddl", "tasks"],
    ),
    "NAMING_SEMANTIC_METADATA_ALIGNMENT": rule_meta(
        name="表名语义段与模型元数据一致",
        severity=SEVERITY_MEDIUM,
        title="表名语义段与模型元数据不一致",
        remediation_summary="修正表名中的业务语义段，或修正模型业务元数据",
        strategy="align_table_name_with_model_metadata",
        edit_scope=["models", "ddl", "tasks"],
    ),
    "NAMING_DDL_FILE_NAME": rule_meta(
        name=FILE_RULE_DDL,
        severity=SEVERITY_LOW,
        title="DDL文件名与表名不一致",
        remediation_summary="重命名DDL文件，使文件名与建表表名一致",
        strategy="rename_file",
        edit_scope=["file_path"],
    ),
    "NAMING_MODEL_FILE_NAME": rule_meta(
        name=FILE_RULE_MODEL_NAME,
        severity=SEVERITY_LOW,
        title="Model文件名与模型name不一致",
        remediation_summary="重命名Model文件，或修正模型name",
        strategy="rename_file_or_model",
        edit_scope=["file_path", "models"],
    ),
    "NAMING_TASK_OUTPUT_NAME": rule_meta(
        name=FILE_RULE_TASK_SQL,
        severity=SEVERITY_LOW,
        title="Task文件名与产出表不一致",
        remediation_summary="重命名Task文件，或修正Task产出表",
        strategy="rename_file_or_task_output",
        edit_scope=["file_path", "tasks"],
    ),
}

NAMING_FILE_RULE_IDS = {
    FILE_RULE_DDL: "NAMING_DDL_FILE_NAME",
    FILE_RULE_MODEL_NAME: "NAMING_MODEL_FILE_NAME",
    FILE_RULE_TASK_SQL: "NAMING_TASK_OUTPUT_NAME",
}


def normalize_score_weights(weights: dict | None = None) -> dict:
    merged = DEFAULT_WEIGHTS.copy()
    extra = {}
    if weights:
        for key, value in weights.items():
            if key == "architecture":
                merged["model_design"] = value
                continue
            if key in DEFAULT_WEIGHTS:
                merged[key] = value
            else:
                extra[key] = value

    invalid = {
        key: value
        for key, value in merged.items()
        if value is None or value < 0
    }
    if invalid:
        invalid_text = ", ".join(
            f"{key}={value}" for key, value in invalid.items()
        )
        raise ValueError(f"权重必须为非负数: {invalid_text}")

    total = sum(merged.values())
    if total <= 0:
        raise ValueError("评分权重之和必须大于 0")

    normalized = {
        key: round(value / total, 6) for key, value in merged.items()
    }
    return {**normalized, **extra}


# 依赖违规定义: 通过 src/tgt 层序号差自动判定
# rank_diff = src_rank - tgt_rank
# 正数 → 反向依赖 (高层→低层, 数据倒流)
# 0     → 同层依赖
# -1    → 相邻上层 (正常, ODS→DWD, DWD→DWS, DWS→ADS)
# -2    → 跳过一层 (DWD→ADS 或 ODS→DWS; DIM→ADS 为合理维度引用)
# -3    → 跳过两层 (ODS→ADS)

ARCH_VIOLATION_RULES = [
    # (rank_diff, description, severity, penalty)
    (3, "反向依赖: 跳过三层(ADS→ODS)", SEVERITY_HIGH, 40),
    (2, "反向依赖: 跳过两层", SEVERITY_HIGH, 30),
    (1, "反向依赖: 跳过一层", SEVERITY_HIGH, 20),
    (0, "同层依赖(非必要)", SEVERITY_LOW, 2),
    (-2, "跳过中间层(DWD→ADS 或 ODS→DWS)", SEVERITY_MEDIUM, 5),
    (-3, "跳过两层(ODS→ADS)", SEVERITY_MEDIUM, 10),
]
