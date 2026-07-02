from __future__ import annotations

import hashlib
import json
import os
import re
import threading
import urllib.error
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Callable

from assess.llm.context_builder import TableContext
from assess.project_facts.entity_metadata import (
    legacy_entity_from_entities,
    legacy_related_entities_from_entities,
    normalize_entities,
)
from assess.project_facts.time_period import (
    is_canonical_time_period,
    normalize_time_period,
)
from config import TEXT_ENCODING

PROMPT_VERSION = "table-inspector-v25"
DEFAULT_API_BASE_URL = "https://api.deepseek.com"
VALID_LAYERS = {"ODS", "DWD", "DWS", "ADS", "DIM", "OTHER"}
VALID_TABLE_TYPES = {"dimension", "fact", "other"}
VALID_DIMENSION_ROLES = {"BASE", "ADDT"}
VALID_DIMENSION_CONTENT_TYPES = {"INFO", "TAG", "TREE"}
METRIC_GROUPING_LAYERS = {"DWD", "DWS"}
COLUMN_GROUPS = (
    "atomic_metrics",
    "derived_metrics",
    "calculated_metrics",
    "dimensions",
    "others",
)
VALIDATION_ERROR_KEYS = (
    "unknown_columns",
    "duplicate_columns",
    "invalid_time_periods",
    "invalid_metric_expressions",
    "missing_primary_entities",
    "invalid_candidate_layers",
    "invalid_dimension_table_type",
)
VALIDATION_WARNING_KEYS = (
    "missing_columns",
    "missing_base_metrics",
    "missing_base_metric_tables",
    "invalid_base_metrics",
    "invalid_base_metric_tables",
    "ambiguous_base_metrics",
    "missing_dimension_entities",
    "missing_metric_metadata",
    "missing_grain_metadata",
)


def _normalized_candidate_layers(
    layers: tuple[str, ...] | list[str],
) -> tuple[str, ...]:
    normalized = []
    for layer in layers or ():
        value = str(layer or "").strip().upper()
        if value in VALID_LAYERS and value != "OTHER" and value not in normalized:
            normalized.append(value)
    return tuple(normalized)


def _normalize_api_base_url(base_url: str) -> str:
    return str(base_url or DEFAULT_API_BASE_URL).strip().rstrip("/")


def _completion_urls(base_url: str) -> list[str]:
    normalized = _normalize_api_base_url(base_url)
    if normalized.endswith("/chat/completions"):
        return [normalized]
    if normalized.endswith("/v1"):
        return [f"{normalized}/chat/completions"]
    urls = [f"{normalized}/chat/completions"]
    if normalized != DEFAULT_API_BASE_URL:
        urls.append(f"{normalized}/v1/chat/completions")
    return urls


def _empty_columns() -> dict[str, list[dict[str, Any]]]:
    return {group: [] for group in COLUMN_GROUPS}


@dataclass
class TableInspectResult:
    table_name: str
    declared_layer: str
    inferred_layer: str  # "ODS" | "DWD" | "DWS" | "ADS" | "DIM" | "OTHER"
    table_type: str  # "dimension" | "fact" | "other"
    confidence: float
    reasoning_steps: list[str]
    columns: dict[str, list[dict[str, Any]]] = field(
        default_factory=_empty_columns
    )
    validation: dict[str, list[str]] = field(default_factory=dict)
    retry_count: int = 0
    inferred_data_domain: str = ""
    inferred_business_area: str = ""
    dimension_role: str = ""
    dimension_content_type: str = ""
    entities: list[dict[str, Any]] = field(default_factory=list)
    entity: dict[str, Any] = field(default_factory=dict)
    related_entities: list[dict[str, Any]] = field(default_factory=list)
    grain: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        self.entities = normalize_entities(
            self.entities,
            self.entity,
            self.related_entities,
        )
        if not self.entity:
            self.entity = legacy_entity_from_entities(self.entities)
        if not self.related_entities:
            self.related_entities = legacy_related_entities_from_entities(
                self.entities
            )

    @property
    def is_violating_declared_layer(self) -> bool:
        """系统根据声明层级和推断层级计算，不由 LLM 返回。"""
        declared = str(self.declared_layer or "").upper()
        inferred = str(self.inferred_layer or "").upper()
        if self.confidence <= 0 or not declared or not inferred:
            return False
        return declared != inferred

    @property
    def is_fact_table(self) -> bool:
        return self.table_type == "fact"

    @property
    def atomic_metrics(self) -> list[dict[str, Any]]:
        return self.columns.get("atomic_metrics", [])

    @property
    def derived_metrics(self) -> list[dict[str, Any]]:
        return self.columns.get("derived_metrics", [])

    @property
    def calculated_metrics(self) -> list[dict[str, Any]]:
        return self.columns.get("calculated_metrics", [])

    @property
    def dimensions(self) -> list[dict[str, Any]]:
        return self.columns.get("dimensions", [])

    @property
    def others(self) -> list[dict[str, Any]]:
        return self.columns.get("others", [])

    @property
    def status(self) -> str:
        """返回 passed/warning/blocked，供回写流程做安全决策。"""
        if self.confidence <= 0:
            return "blocked"
        if any(self.validation.get(key) for key in VALIDATION_ERROR_KEYS):
            return "blocked"
        if any(self.validation.get(key) for key in VALIDATION_WARNING_KEYS):
            return "warning"
        return "passed"


def build_prompt(ctx: TableContext) -> str:
    candidate_layers = _normalized_candidate_layers(ctx.candidate_layers)
    candidate_layer_text = (
        "|".join(candidate_layers) or "ODS|DWD|DWS|ADS|DIM|OTHER"
    )
    prompt = """你是一位资深数据仓库架构师和指标治理专家。你的任务是根据给定的表结构、ETL 加工逻辑和血缘关系，完成一次统一巡检:
1. 客观推断这张表真实应该归属的数仓分层。
2. 判断它的物理表类型（维度表/事实表/其他）。
3. 识别 entities、grain 元数据候选。
4. 如果你判断该表真实层级是 DWD 或 DWS 且它是事实表，则对字段分组识别原子指标、派生指标、衍生指标、维度字段和其他字段；冷启动时原始配置可能是 OTHER，也必须按 inferred_layer 做字段分组。

## 数仓分层判定标准
- ODS (贴源层): 直接同步业务库，通常不含复杂的转化逻辑，数据粒度与源库完全一致。
- DWD (明细宽表层): 对 ODS 进行数据清洗、维度退化(多表 JOIN 拉宽)，但**保持事务明细粒度，严禁包含聚合(GROUP BY)操作**。
- DWS (汇总层): 包含明确的聚合操作(GROUP BY/SUM/COUNT)，用于计算公共维度下的周期性指标，通常具备可复用特征；冷启动血缘不完整时，下游为 0 不能单独否定 DWS。
- ADS (应用层): 面向最终报表、业务大屏、专题分析或运营看板的定制化数据，可能包含复杂的衍生指标；下游通常不再被其他数据表引用，但出度为 0 只是弱信号，不能覆盖 ETL、粒度和表语义证据。典型应用输出形态包括 TOPN/排名、ROI、RFM、预警、绩效看板、按人群/地域/分群的 by_* 分析表，以及没有明确周期复用语义的 summary 应用表。
- DIM (公共维度表): 记录实体属性，主键通常为单一实体 ID，被其他宽表广泛 LEFT JOIN。

"""
    if candidate_layers:
        prompt += f"""## 本轮候选层约束
- 本轮只允许在 {", ".join(candidate_layers)} 中选择 inferred_layer，JSON 中不得返回 ODS、ADS 或 OTHER。
- ODS 和 ADS 已由目录、配置或外部参数确定；本轮任务只判断中间层。
- 如果表看起来贴源但不在 ODS 固定目录中，请根据粒度和实体语义在 DWD/DIM 中选择最合理的一层，不要返回 ODS。
- 如果表看起来像应用输出但本轮候选层不包含 ADS，请先检查它是否是公共汇总口径；有 GROUP BY 且按实体/周期/公共维度沉淀的汇总事实表，应优先判为 DWS，即使下游引用数为 0。
- 下游被引用次数为 0 在冷启动场景中只能作为弱信号，不能把公共汇总表单独推到 ADS。

"""
    prompt += f"""
## 表类型判定标准
- dimension: 维度表。描述可被事实表引用的业务实体属性、层级、状态或主数据，缓慢变化，常常作为维表被 JOIN。
- fact: 事实表或汇总事实表。记录业务事件/交易，或按公共维度汇总业务过程，包含可度量字段，通常有时间分区。
- other: 其他类型。

## 维表分类标准
当 table_type=dimension 或 inferred_layer=DIM 时，必须额外判断维表内容形态和维表建设角色。
- dimension_content_type=INFO: 属性信息维表。描述实体基础属性、业务属性、状态、日期、名称、说明等。
- dimension_content_type=TAG: 标签维表。描述规则、指标、模型或统计加工形成的标签、分层、评分、画像、偏好、风险等级等。
- dimension_content_type=TREE: 树形维表。描述父子节点、层级、路径、上下级归属、祖先节点、叶子节点，支持上卷和下钻。
- dimension_role=BASE: 主维度。描述实体最核心、最标准、公共复用的身份和基础信息。
- dimension_role=ADDT: 辅维度。描述实体补充信息、扩展属性、关系信息、场景化属性或低频属性。
若当前表不是维度表，dimension_role 和 dimension_content_type 都返回空字符串。

## 业务过程与语义主题边界
- business_process 只适用于事实表或汇总事实表，用来描述发生了什么可度量业务事件/活动；判断依据应是事件动作、事实行、度量字段、时间粒度和可汇总口径，而不是表名里出现的业务名词。
- dimension 表不得为了填充业务过程而生成“实体主语 + 管理/运营”式过程名；若表只表达管理/运营/主数据/资料维护/属性集合，它们更可能是语义主题、业务主题或实体管理域。
- semantic_subject 表示维度/实体属性表的语义主题，通常对应维表主实体编码；它不是业务过程，也不应被写入指标字段的 business_process。
- 表名或描述中含有 MANAGEMENT、OPERATION、PROFILE、MASTER、INFO 等模式时，必须先检查是否存在可度量业务事件；没有事件事实和指标时，优先视为语义主题/业务主题，不要归为严格的业务过程。
- 字段级 business_process 若需要填写，应是可代码化的大写下划线短语，表达“动作/事件 + 业务结果或业务对象”的过程；不能仅由实体主语、管理/运营词或表主题词组成。
- 如果提供了已确认业务语义目录，business_process 和 entities[].code 应优先复用目录中的 code；若没有合适 code，可以返回新的大写下划线候选，但必须由当前表的事件事实、指标口径或主实体证据支撑。
- 本次巡检 JSON 不返回 semantic_subject 顶层字段；这条规则用于避免把维表主题误填到指标字段的 business_process。catalog 初始化或 models 回写时可将 dimension 表主实体转为 semantic_subject。

## 指标字段分组标准
- atomic_metrics: 基于某一业务过程下不可再拆分的基础指标口径，通常由业务过程、度量对象和标准统计方式构成。对事件标识或实体标识字段做 COUNT/COUNT DISTINCT 生成基础计数口径时，应归 atomic_metrics；不包含比率、分数、多个度量组合、同一明细行内多个基础要素的算术组合、结果性明细度量、复杂 CASE/窗口函数/模型计算等二次计算。字段是否为原子指标不能只看 ETL 是否直接透传，必须结合字段语义和业务定义判断。business_process 仅当当前表是 fact/DWD fact/DWS 汇总事实且字段是指标时填写；dimension/属性字段返回空字符串。尽量填写 business_process/action/measure。
- derived_metrics: 放度量型派生指标，即一个已存在的原子指标 + 多个修饰词(可选) + 时间周期/统计粒度/限定条件。它本质上仍是对原子指标统计范围的限定，没有改变指标计算逻辑。DWS 汇总表中，如果字段是对上游已存在的 atomic_metrics 做 SUM/AVG/MIN/MAX 等标准聚合，并叠加维度、周期或限定条件，通常应归 derived_metrics，而不是 atomic_metrics。尽量填写 base_metric/modifiers/time_period/expression。
- calculated_metrics: 只放度量型衍生指标，即基于一个或多个已有指标，通过公式、规则、模型或二次计算得到的新指标，通常产生新的业务含义。包括比率、分数、差值、绝对值、风险等级、窗口函数、复杂 CASE 规则、多字段组合计算、同一明细行内多个基础要素组合后的结果度量等。即使字段从上游直接透传或上游已经预先算好，只要字段注释、字段级血缘或业务语义表明它是已物化的结果性度量，而不是独立观测到的基础计量，也应按 calculated_metrics 判断。DWS 汇总表中，如果字段是对上游 calculated_metrics 再聚合，也应归 calculated_metrics。尽量填写 expression/derived_from。
- dimensions: 主键、外键、日期、时间、状态、标签、枚举、布尔标志、退化维度、实体属性、非加性属性等分析维度字段。价格、成本、费率、汇率、系数、阈值等非加性输入属性如果主要作为切片、描述或其他指标计算输入，而不是独立统计口径，应放入 dimensions；即使它们由 DATE_FORMAT、CASE WHEN 或其他表达式生成，只要用于切片/过滤/分组而不是作为度量，也应放入 dimensions。
- others: 审计字段、技术字段、无法判断字段。
- DWD 事实表只能包含 atomic_metrics；derived_metrics 和 calculated_metrics 都属于 DWD 违规风险。
- DWS 事实表通常承载 derived_metrics；不要因为 DWS 表包含派生指标而判为违规。

## 度量可加性约束
- atomic_metrics 必须是可被独立观测、可计数或可按事实粒度直接汇总形成业务总量的基础口径。
- 非加性输入属性只用于描述、切片或参与其他公式，不能作为 atomic_metrics。
- 对非加性输入属性做补值、回填、估算、格式标准化或缺失值兜底，只是在修正属性取值，不会让字段变成 calculated_metrics；除非该字段本身已经表达新的业务结果口径，否则应继续归 dimensions。
- 已物化的明细行结果度量即使来自上游直接透传，也不能作为 atomic_metrics；如果它表示当前事实行的业务结果，应归 calculated_metrics。
- 判断一个字段是否为 atomic_metrics 时，直接透传优先级低于可加性、字段注释、字段级血缘和业务语义。

## DWS 指标分类优先级
1. 对事件标识或实体标识字段做 COUNT/COUNT DISTINCT 生成基础计数指标时，优先归 atomic_metrics；分组维度和统计日期只表达当前汇总表粒度，不应单独导致它变成 derived_metrics。
2. 对上游 atomic_metrics 做 SUM/AVG/MIN/MAX 等聚合，并叠加维度、周期或限定条件时，归 derived_metrics。
3. 对上游 calculated_metrics 做聚合，或当前字段表达式包含多个度量组合时，归 calculated_metrics。
4. 判断上游字段类型时，优先参考“上游指标分组”；如果没有上游指标分组，再结合字段角色、注释、ETL 表达式和业务语义判断，不要套用字段名示例。
5. 对字段做分组时，优先使用字段级血缘表达式判断来源和计算关系；直接透传只能说明当前 ETL 没有再次计算，不能否定字段自身已经是结果性度量。

## 指标 expression 与 grain 边界
- metric.expression 只填写指标计算公式，例如 SUM(subtotal)、COUNT(DISTINCT order_id)、SUM(subtotal - discount)。
- 不要在 metric.expression 中写 GROUP BY；不要在 metric.expression 中写“按...分组”、"by ..." 等粒度说明。
- 聚合粒度由表级 grain 表达；grain.entities 和 grain.time_column 应与 SQL GROUP BY 的业务粒度对齐。
- 如果 SQL 存在 GROUP BY，只从目标指标字段自身的 SELECT 表达式提取 metric.expression；GROUP BY 字段、时间字段、实体字段和中文粒度说明都不要写入 metric.expression。
- 输出前逐项检查所有 metric.expression：不得包含 GROUP BY、分组字段列表、时间粒度字段、实体粒度字段或中文粒度描述；若包含，应删除这些粒度片段，只保留指标计算公式。

## entities、grain 元数据识别
- entities 表示当前模型中参与语义关联的实体键，借鉴 dbt Semantic Layer entity。每个实体返回 code、type 和 key_columns。
- type 可取 primary、unique、foreign、natural。primary 表示当前表主实体键；unique 表示当前表内唯一但不是主实体；foreign 表示当前表引用其他实体的键；natural 表示拉链/快照表中标识业务实体但单独不唯一的自然键。
- 维度型/实体型表应至少返回一个 type=primary 的主实体；如果当前表承载上级、归属或层级实体，则用 type=foreign 并带 relationship。
- DWD fact 应优先识别当前事实行的主实体并返回 type=primary，例如订单明细、交易流水、支付事件、库存快照行等；复合业务键可以完整写入 key_columns，不要因为主键不是单列就放弃 primary。
- DWD fact 中被引用的客户、商品、门店、活动等上下文对象应返回 type=foreign。
- DWS 汇总事实表中的实体通常为 type=foreign，key_columns 是当前表中表示该实体的字段名；DWS 的行粒度由 grain 描述。
- grain 主要适用于 DWS 汇总事实表。若当前表是 DWS fact，应返回粒度实体 grain.entities、时间字段 time_column 和时间周期 time_period；DWD fact 只有在没有清晰 primary entity 但能由业务键/日期明确行粒度时才返回 grain；其他表 grain 返回空对象。
- grain.entities 必须引用当前返回的 entities[].code；它应来自粒度 key 对应的主要业务实体，不要把时间字段、状态、品牌、父级属性等普通维度属性放入 grain.entities。
- grain.entities 应返回完整的粒度实体集合；若粒度涉及多个实体，不要为了贴合 TABLE_DWS 命名段而裁剪 entities。
- time_period 只允许 D/W/M/Q/Y/S，含义分别为日/周/月/季/年/快照；不得返回中文、英文单词或 1d/1m 等窗口写法，无法判断时返回空字符串。
- 不要返回 grain.keys；粒度字段由 grain.entities 引用的 entities[].key_columns 加上 time_column 推导。
- 如果无法高置信判断 entities 或 grain，对应数组或对象返回空数组/空对象，不要编造字段或实体编码。

## 表级特征信息
- 原始表名: {ctx.table_name}
- 原始配置层级: {ctx.layer}
- 原始配置数据域: {ctx.declared_data_domain or "未配置"}
- 原始配置业务板块: {ctx.declared_business_area or "未配置"}
- 下游被引用次数: {len(ctx.downstream_tables)}
- 距 ODS 最小跳数: {ctx.depth_from_ods}

## DDL
{ctx.ddl}

"""
    if ctx.project_context:
        prompt += f"""## 项目背景说明
以下背景仅作为辅助语义，用于理解业务名词、核心实体和指标口径；不能覆盖 DDL、ETL、血缘和字段级血缘等结构化证据。
{ctx.project_context}

"""
    if ctx.business_domain_options:
        prompt += f"""## 数据域与业务板块字典
请根据表名、DDL、ETL 和血缘语义，判断该表最合理的数据域与业务板块。
- 数据域只适用于 DWD 层。当前表若不是 DWD，inferred_data_domain 必须返回空字符串。
- 业务板块只适用于 DWD 和 DWS 层。当前表若不是 DWD/DWS，inferred_business_area 必须返回空字符串。
- 对适用层，inferred_data_domain 必须返回数据域编号，如 "04"；如果无法明确判断，可返回“其它”数据域编号。
- 对适用层，inferred_business_area 必须返回业务板块简写，如 "PAYM"；如果无法明确判断，可返回“其它”业务板块简写。
- 若原始配置与业务语义不一致，应返回你推断的正确值。

可选字典:
{json.dumps(ctx.business_domain_options, ensure_ascii=False, indent=2)}

"""
    else:
        prompt += """## 数据域与业务板块候选
未提供数据域与业务板块字典，本轮允许进行轻量发现:
- 数据域只适用于 DWD 层。当前表若不是 DWD，inferred_data_domain 必须返回空字符串。
- 业务板块只适用于 DWD 和 DWS 层。当前表若不是 DWD/DWS，inferred_business_area 必须返回空字符串。
- 若当前表语义明确，可以返回新的大写下划线候选 code；不确定时返回空字符串。
- 候选 code 应表达业务域或板块语义，不要照抄表名，不要填管理/运营这类泛化词。

"""
    if ctx.business_semantics_options:
        prompt += f"""## 已确认业务语义目录
请把下列目录作为人工确认过的治理输入使用。
- 事实表/汇总事实表的指标字段若能匹配某个业务过程，business_process 必须优先复用目录中的 code。
- 维度表的 entities[].code 若能匹配某个语义主题，必须优先复用目录中的 code。
- 若没有合适 code，可以返回新的大写下划线候选；不要为了贴合目录而把维度主题填成业务过程。

可选目录:
{json.dumps(ctx.business_semantics_options, ensure_ascii=False, indent=2)}

"""
    if ctx.etl_sql:
        prompt += f"## ETL 加工逻辑\n{ctx.etl_sql}\n\n"

    prompt += f"""## 血缘关系
上游表: {", ".join(ctx.upstream_tables) if ctx.upstream_tables else "无"}
下游表: {", ".join(ctx.downstream_tables) if ctx.downstream_tables else "无"}

## 字段级血缘
{json.dumps(ctx.column_lineage, ensure_ascii=False, indent=2) if ctx.column_lineage else "无"}

## 上游指标分组
{json.dumps(ctx.upstream_metric_groups, ensure_ascii=False, indent=2) if ctx.upstream_metric_groups else "无"}

## 思考步骤
1. 首先分析 ETL_SQL 中是否包含 GROUP BY 等聚合操作，如果有，排除 DWD 和 ODS。
2. 观察下游被引用次数。出度为 0 只作为弱信号：聚合且口径公共的表仍可能是 DWS，明细事实表仍可能是 DWD；存在 TOPN/ROI/RFM/预警/绩效/看板/by_* 分析/无周期 summary 等明确应用输出语义时，应倾向 ADS。
3. 判断是否为 dimension（主键是否为实体属性）。
4. 如果 inferred_layer 是 DWD 或 DWS 且表类型为 fact，再按字段语义、DDL 注释、ETL 表达式和业务过程分组；不要因为原始配置层级是 OTHER 而跳过指标字段分组。

请严格返回 JSON 格式数据，只允许返回下方 JSON schema 中列出的顶层字段: inferred_layer、table_type、inferred_data_domain、inferred_business_area、dimension_role、dimension_content_type、entities、grain、confidence、reasoning_steps、columns。
不要返回 Markdown，不要返回额外解释，不要新增任何字段。
如果 inferred_layer 不是 DWD/DWS 或 table_type 不是 fact，columns 下五个数组都返回空数组。

{{
  "inferred_layer": "{candidate_layer_text}",
  "table_type": "dimension|fact|other",
  "inferred_data_domain": "已确认数据域编号或新的大写下划线候选 code；不适用或不确定时为空字符串",
  "inferred_business_area": "已确认业务板块简写或新的大写下划线候选 code；不适用或不确定时为空字符串",
  "dimension_role": "BASE|ADDT",
  "dimension_content_type": "INFO|TAG|TREE",
  "entities": [
    {{
      "code": "实体编码，如 PROD；不适用或无法判断时返回空数组",
      "type": "primary|unique|foreign|natural",
      "name": "实体中文名，如 商品；无法判断则为空字符串",
      "key_columns": ["当前表中表示该实体的字段名"],
      "relationship": {{
        "type": "many_to_one|one_to_many|one_to_one|hierarchy",
        "from_entity": "当前表主实体编码，如 PROD；不适用则为空字符串"
      }}
    }}
  ],
  "grain": {{
    "entities": ["粒度实体编码，如 PROD"],
    "time_column": "时间粒度字段名，如 stat_date；无则为空字符串",
    "time_period": "D|W|M|Q|Y|S，无法判断则为空字符串"
  }},
  "confidence": 0.0,
  "reasoning_steps": ["分析步骤1...", "分析步骤2..."],
  "columns": {{
    "atomic_metrics": [
      {{
        "name": "字段名",
        "data_type": "字段类型",
        "business_process": "业务过程，无法判断则为空字符串",
        "action": "动作动词，无法判断则为空字符串",
        "measure": "度量名词，无法判断则为空字符串",
        "description": "简短中文描述",
        "reason": "分类理由",
        "confidence": 0.0
      }}
    ],
    "derived_metrics": [
      {{
        "name": "字段名",
        "data_type": "字段类型",
        "business_process": "业务过程 code，无法判断则为空字符串",
        "base_metric": "对应原子指标名，无法判断则为空字符串",
        "base_metric_table": "对应原子指标所在上游表名，无法判断则为空字符串",
        "modifiers": ["修饰词，如区域/渠道/状态，无法判断则为空数组"],
        "time_period": "D|W|M|Q|Y|S，无法判断则为空字符串",
        "expression": "统计范围限定表达式，无法判断则为空字符串",
        "description": "简短中文描述",
        "reason": "分类理由",
        "confidence": 0.0
      }}
    ],
    "calculated_metrics": [
      {{
        "name": "字段名",
        "data_type": "字段类型",
        "business_process": "业务过程 code，无法判断则为空字符串",
        "expression": "衍生表达式，无法判断则为空字符串",
        "derived_from": ["来源字段"],
        "description": "简短中文描述",
        "reason": "分类理由",
        "confidence": 0.0
      }}
    ],
    "dimensions": [
      {{
        "name": "字段名",
        "dimension_type": "primary_key|foreign_key|date|time|status|attribute|degenerate|other",
        "data_type": "字段类型",
        "description": "简短中文描述",
        "reason": "分类理由",
        "confidence": 0.0
      }}
    ],
    "others": [
      {{
        "name": "字段名",
        "role": "audit|technical|unknown|other",
        "data_type": "字段类型",
        "description": "简短中文描述",
        "reason": "分类理由",
        "confidence": 0.0
      }}
    ]
  }}
}}
"""
    return prompt


def build_retry_prompt(
    ctx: TableContext, result: TableInspectResult, ddl_columns: set[str]
) -> str:
    """基于校验失败结果构造重试 prompt。"""
    retry_context = {
        "validation": result.validation,
        "status": result.status,
        "ddl_columns": sorted(ddl_columns),
    }
    return (
        build_prompt(ctx)
        + f"""

## 上次返回结果校验未通过
{json.dumps(retry_context, ensure_ascii=False, indent=2)}

请重新返回完整 JSON，并严格修正:
- 字段名必须来自 ddl_columns，不要编造字段。
- 同一个字段只能出现在 atomic_metrics / derived_metrics / calculated_metrics / dimensions / others 中的一个分组。
- 如果表是 DWD/DWS fact，DDL 中每个字段都必须进入且仅进入一个分组。
- derived_metrics 中每个指标必须填写 base_metric；能判断来源表时填写 base_metric_table，且 base_metric 必须来自该表 atomic_metrics。
- invalid_time_periods 中列出的 time_period 必须改为 D/W/M/Q/Y/S 之一；不要返回中文、英文单词或 1d/1m 等写法。
- invalid_metric_expressions 中列出的 expression 必须删除 GROUP BY、按...分组、by ... 等粒度说明，只保留指标计算公式。
- missing_primary_entities 表示 DWD fact 缺少主实体；必须为当前事实行/事件/明细行补充至少一个 type=primary 的 entities 项。
- invalid_candidate_layers 表示 inferred_layer 不在本轮候选层中；必须从本轮候选层中重选，不能返回 ODS/ADS/OTHER。
- invalid_dimension_table_type 表示 DIM 层不能返回 fact/other；必须修正 table_type 或重判层级。
- missing_dimension_entities 表示维度表缺少主实体；如能判断，补充至少一个 type=primary 的 entities 项。
- missing_metric_metadata 表示 DWS fact 缺少指标分组；如能判断，把度量字段放入 atomic_metrics、derived_metrics 或 calculated_metrics。
- missing_grain_metadata 表示 DWS fact 缺少表级 grain；如能判断，补充 grain.entities、time_column 或 time_period 中可从 SQL/DDL 判断的部分。
- 不要返回 Markdown，不要返回额外解释。
"""
    )


def _strip_markdown_json(content: str) -> str:
    text = content.strip()
    if text.startswith("```"):
        first_newline = text.find("\n")
        if first_newline >= 0:
            text = text[first_newline + 1 :]
        if text.endswith("```"):
            text = text[:-3]
    return text.strip()


def _extract_json_object(content: str) -> str:
    text = content.strip()
    start = text.find("{")
    end = text.rfind("}")
    if start < 0 or end <= start:
        return text
    return text[start : end + 1].strip()


def _repair_unescaped_json_string_quotes(content: str) -> str:
    repaired: list[str] = []
    in_string = False
    escaped = False
    length = len(content)

    for index, char in enumerate(content):
        if escaped:
            repaired.append(char)
            escaped = False
            continue

        if char == "\\":
            repaired.append(char)
            if in_string:
                escaped = True
            continue

        if char != '"':
            repaired.append(char)
            continue

        if not in_string:
            in_string = True
            repaired.append(char)
            continue

        next_index = index + 1
        while next_index < length and content[next_index].isspace():
            next_index += 1
        next_char = content[next_index] if next_index < length else ""
        if next_char in {":", ",", "]", "}"} or next_char == "":
            in_string = False
            repaired.append(char)
        else:
            repaired.append('\\"')

    return "".join(repaired)


def _loads_llm_json(content: str) -> dict[str, Any]:
    candidates = [content]
    extracted = _extract_json_object(content)
    if extracted != content:
        candidates.append(extracted)

    last_error: json.JSONDecodeError | None = None
    for candidate in candidates:
        for raw in (candidate, _repair_unescaped_json_string_quotes(candidate)):
            try:
                data = json.loads(raw)
            except json.JSONDecodeError as exc:
                last_error = exc
                continue
            if isinstance(data, dict):
                return data
            raise json.JSONDecodeError("JSON 顶层必须是对象", raw, 0)

    if last_error is not None:
        raise last_error
    raise json.JSONDecodeError("未找到 JSON 对象", content, 0)


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _safe_list(value: Any) -> list[str]:
    if isinstance(value, list):
        return [str(item) for item in value if str(item).strip()]
    if value in (None, ""):
        return []
    return [str(value)]


def _safe_str(value: Any) -> str:
    return str(value or "").strip()


def _normalize_time_period_or_raw(value: Any) -> str:
    text = _safe_str(value)
    return normalize_time_period(text) or text


def _safe_dict(value: Any) -> dict[str, Any]:
    return dict(value) if isinstance(value, dict) else {}


def _safe_dict_list(value: Any) -> list[dict[str, Any]]:
    if not isinstance(value, list):
        return []
    return [dict(item) for item in value if isinstance(item, dict)]


def _normalize_grain(value: Any) -> dict[str, Any]:
    grain = _safe_dict(value)
    if not grain:
        return {}

    keys = _safe_list(grain.get("keys"))
    entities = _safe_list(grain.get("entities"))
    time_column = _safe_str(grain.get("time_column"))
    time_period = _normalize_time_period_or_raw(grain.get("time_period"))

    # Treat placeholder payloads as empty grain metadata.
    if not keys and not entities and not time_column and not time_period:
        return {}

    normalized = {}
    if keys:
        normalized["keys"] = keys
    if entities:
        normalized["entities"] = entities
    if time_column:
        normalized["time_column"] = time_column
    if time_period:
        normalized["time_period"] = time_period
    return normalized


def _valid_layer(value: Any) -> str:
    layer = str(value or "OTHER").upper()
    return layer if layer in VALID_LAYERS else "OTHER"


def _valid_table_type(value: Any) -> str:
    table_type = str(value or "other").strip()
    return table_type if table_type in VALID_TABLE_TYPES else "other"


def _valid_dimension_role(value: Any) -> str:
    role = str(value or "").strip().upper()
    return role if role in VALID_DIMENSION_ROLES else ""


def _valid_dimension_content_type(value: Any) -> str:
    content_type = str(value or "").strip().upper()
    return (
        content_type if content_type in VALID_DIMENSION_CONTENT_TYPES else ""
    )


def _normalize_group_item(
    raw: dict[str, Any], fields: tuple[str, ...]
) -> dict:
    name = str(raw.get("name") or raw.get("column_name") or "").strip()
    if not name:
        return {}

    item = {"name": name}
    for field_name in fields:
        if field_name == "name":
            continue
        if field_name == "confidence":
            item[field_name] = _safe_float(raw.get(field_name))
        elif field_name in ("derived_from", "modifiers"):
            item[field_name] = _safe_list(raw.get(field_name))
        elif field_name == "time_period":
            item[field_name] = _normalize_time_period_or_raw(
                raw.get(field_name)
            )
        else:
            item[field_name] = str(raw.get(field_name) or "")
    return item


def _normalize_columns(raw_columns: Any) -> dict[str, list[dict[str, Any]]]:
    columns = _empty_columns()
    if not isinstance(raw_columns, dict):
        return columns

    group_fields = {
        "atomic_metrics": (
            "name",
            "data_type",
            "business_process",
            "action",
            "measure",
            "description",
            "reason",
            "confidence",
        ),
        "derived_metrics": (
            "name",
            "data_type",
            "business_process",
            "base_metric",
            "base_metric_table",
            "modifiers",
            "time_period",
            "expression",
            "description",
            "reason",
            "confidence",
        ),
        "calculated_metrics": (
            "name",
            "data_type",
            "business_process",
            "expression",
            "derived_from",
            "description",
            "reason",
            "confidence",
        ),
        "dimensions": (
            "name",
            "dimension_type",
            "data_type",
            "description",
            "reason",
            "confidence",
        ),
        "others": (
            "name",
            "role",
            "data_type",
            "description",
            "reason",
            "confidence",
        ),
    }

    for group_name, fields in group_fields.items():
        raw_items = raw_columns.get(group_name, []) or []
        if not isinstance(raw_items, list):
            continue
        for raw_item in raw_items:
            if not isinstance(raw_item, dict):
                continue
            item = _normalize_group_item(raw_item, fields)
            if item:
                columns[group_name].append(item)
    return columns


def parse_response(
    table_name: str, response: dict, declared_layer: str = ""
) -> TableInspectResult:
    content = (
        response.get("choices", [{}])[0]
        .get("message", {})
        .get("content", "")
        .strip()
    )
    content = _strip_markdown_json(content)

    try:
        data = _loads_llm_json(content)
        return TableInspectResult(
            table_name=table_name,
            declared_layer=str(declared_layer or ""),
            inferred_layer=_valid_layer(data.get("inferred_layer")),
            table_type=_valid_table_type(data.get("table_type")),
            confidence=_safe_float(data.get("confidence")),
            reasoning_steps=list(data.get("reasoning_steps", []) or []),
            columns=_normalize_columns(data.get("columns")),
            inferred_data_domain=_safe_str(data.get("inferred_data_domain")),
            inferred_business_area=_safe_str(
                data.get("inferred_business_area")
            ).upper(),
            dimension_role=_valid_dimension_role(data.get("dimension_role")),
            dimension_content_type=_valid_dimension_content_type(
                data.get("dimension_content_type")
            ),
            entities=normalize_entities(
                data.get("entities"),
                data.get("entity"),
                data.get("related_entities"),
            ),
            entity=_safe_dict(data.get("entity")),
            related_entities=_safe_dict_list(data.get("related_entities")),
            grain=_normalize_grain(data.get("grain")),
        )
    except json.JSONDecodeError as e:
        return TableInspectResult(
            table_name=table_name,
            declared_layer=str(declared_layer or ""),
            inferred_layer="OTHER",
            table_type="other",
            confidence=0.0,
            reasoning_steps=[f"JSON 解析失败: {e}\n原文: {content}"],
        )


def result_to_dict(result: TableInspectResult) -> dict[str, Any]:
    return {
        "table_name": result.table_name,
        "declared_layer": result.declared_layer,
        "inferred_layer": result.inferred_layer,
        "table_type": result.table_type,
        "inferred_data_domain": result.inferred_data_domain,
        "inferred_business_area": result.inferred_business_area,
        "dimension_role": result.dimension_role,
        "dimension_content_type": result.dimension_content_type,
        "confidence": result.confidence,
        "reasoning_steps": result.reasoning_steps,
        "columns": result.columns,
        "entities": result.entities,
        "entity": result.entity,
        "related_entities": result.related_entities,
        "grain": result.grain,
        "validation": result.validation,
        "status": result.status,
        "retry_count": result.retry_count,
        "is_violating_declared_layer": result.is_violating_declared_layer,
    }


def result_to_cache_dict(result: TableInspectResult) -> dict[str, Any]:
    """仅保存恢复巡检结果所需字段，派生字段由读取后重新计算。"""
    return {
        "table_name": result.table_name,
        "declared_layer": result.declared_layer,
        "inferred_layer": result.inferred_layer,
        "table_type": result.table_type,
        "inferred_data_domain": result.inferred_data_domain,
        "inferred_business_area": result.inferred_business_area,
        "dimension_role": result.dimension_role,
        "dimension_content_type": result.dimension_content_type,
        "confidence": result.confidence,
        "reasoning_steps": result.reasoning_steps,
        "columns": result.columns,
        "entities": result.entities,
        "entity": result.entity,
        "related_entities": result.related_entities,
        "grain": result.grain,
        "validation": result.validation,
        "retry_count": result.retry_count,
    }


def dict_to_result(
    data: dict[str, Any], *, table_name: str = "", declared_layer: str = ""
) -> TableInspectResult:
    return TableInspectResult(
        table_name=str(data.get("table_name") or table_name),
        declared_layer=str(data.get("declared_layer") or declared_layer),
        inferred_layer=_valid_layer(data.get("inferred_layer")),
        table_type=_valid_table_type(data.get("table_type")),
        confidence=_safe_float(data.get("confidence")),
        reasoning_steps=list(data.get("reasoning_steps", []) or []),
        columns=_normalize_columns(data.get("columns")),
        entities=normalize_entities(
            data.get("entities"),
            data.get("entity"),
            data.get("related_entities"),
        ),
        entity=_safe_dict(data.get("entity")),
        related_entities=_safe_dict_list(data.get("related_entities")),
        grain=_normalize_grain(data.get("grain")),
        validation=_normalize_validation(data.get("validation")),
        retry_count=int(data.get("retry_count", 0) or 0),
        inferred_data_domain=_safe_str(data.get("inferred_data_domain")),
        inferred_business_area=_safe_str(
            data.get("inferred_business_area")
        ).upper(),
        dimension_role=_valid_dimension_role(data.get("dimension_role")),
        dimension_content_type=_valid_dimension_content_type(
            data.get("dimension_content_type")
        ),
    )


def _normalize_validation(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    normalized = {}
    for key in (
        "unknown_columns",
        "duplicate_columns",
        "missing_columns",
        "missing_base_metrics",
        "missing_base_metric_tables",
        "invalid_base_metrics",
        "invalid_base_metric_tables",
        "ambiguous_base_metrics",
        "invalid_time_periods",
        "invalid_metric_expressions",
        "missing_primary_entities",
        "invalid_candidate_layers",
        "invalid_dimension_table_type",
        "missing_dimension_entities",
        "missing_metric_metadata",
        "missing_grain_metadata",
    ):
        raw_items = value.get(key, []) or []
        if isinstance(raw_items, list):
            normalized[key] = [str(item) for item in raw_items]
    return normalized


def _extract_ddl_column_names(ddl: str) -> set[str]:
    """从 DDL 中解析字段名，用于校验 LLM 字段分组结果。"""
    if not ddl.strip():
        return set()
    try:
        import sqlglot
        from sqlglot import exp

        columns = set()
        for stmt in sqlglot.parse(ddl, dialect="doris"):
            if isinstance(stmt, exp.Create) and isinstance(
                stmt.this, exp.Schema
            ):
                for col in stmt.this.expressions:
                    if isinstance(col, exp.ColumnDef):
                        columns.add(col.this.name)
        return columns
    except Exception:
        return set()


def validate_columns(
    result: TableInspectResult, ddl_columns: set[str]
) -> dict[str, list[str]]:
    """校验 LLM 返回字段是否存在、是否重复、事实表字段是否遗漏。"""
    if not ddl_columns:
        return {}

    grouped_names = []
    for group in COLUMN_GROUPS:
        for item in result.columns.get(group, []):
            grouped_names.append(str(item.get("name") or ""))

    seen = set()
    duplicates = set()
    for name in grouped_names:
        if not name:
            continue
        if name in seen:
            duplicates.add(name)
        seen.add(name)

    returned = {name for name in grouped_names if name}
    validation = {
        "unknown_columns": sorted(returned - ddl_columns),
        "duplicate_columns": sorted(duplicates),
        "missing_columns": [],
    }
    if (
        (
            result.declared_layer in METRIC_GROUPING_LAYERS
            or result.inferred_layer in METRIC_GROUPING_LAYERS
        )
        and result.is_fact_table
    ):
        validation["missing_columns"] = sorted(ddl_columns - returned)
    return validation


def validate_time_periods(
    result: TableInspectResult,
) -> dict[str, list[str]]:
    """校验 LLM 返回的 time_period 是否已使用规范枚举值。"""
    invalid = []
    grain_period = str(result.grain.get("time_period") or "").strip()
    if (
        grain_period
        and not is_canonical_time_period(grain_period)
        and not normalize_time_period(grain_period)
    ):
        invalid.append(f"grain.time_period={grain_period}")

    for index, metric in enumerate(result.derived_metrics):
        period = str(metric.get("time_period") or "").strip()
        if (
            period
            and not is_canonical_time_period(period)
            and not normalize_time_period(period)
        ):
            invalid.append(f"derived_metrics[{index}].time_period={period}")

    return {"invalid_time_periods": invalid} if invalid else {}


def validate_metric_expressions(
    result: TableInspectResult,
) -> dict[str, list[str]]:
    """校验指标表达式没有混入表粒度或分组描述。"""
    invalid = []
    pattern = re.compile(
        r"\bGROUP\s+BY\b|按.+分组|\bby\s+[^()]+$",
        re.IGNORECASE,
    )
    for group_name in ("derived_metrics", "calculated_metrics"):
        metrics = result.columns.get(group_name, []) or []
        for index, metric in enumerate(metrics):
            expression = str(metric.get("expression") or "").strip()
            if expression and pattern.search(expression):
                invalid.append(
                    f"{group_name}[{index}].expression={expression}"
                )
    return {"invalid_metric_expressions": invalid} if invalid else {}


def validate_primary_entities(
    result: TableInspectResult,
) -> dict[str, list[str]]:
    """校验事实明细表必须返回当前事实行主实体。"""
    if (
        result.declared_layer != "DWD"
        and result.inferred_layer != "DWD"
    ) or not result.is_fact_table:
        return {}
    has_primary = any(
        str(entity.get("type") or "").strip().lower() == "primary"
        for entity in result.entities
        if isinstance(entity, dict)
    )
    if has_primary:
        return {}
    return {
        "missing_primary_entities": [
            "DWD fact必须返回至少一个type=primary的entities项"
        ]
    }


def validate_candidate_layer(
    result: TableInspectResult, candidate_layers: tuple[str, ...] | list[str]
) -> dict[str, list[str]]:
    """校验结果层级是否落在调用方限定的候选层内。"""
    allowed = set(_normalized_candidate_layers(candidate_layers))
    if not allowed or result.inferred_layer in allowed:
        return {}
    return {
        "invalid_candidate_layers": [
            (
                f"inferred_layer={result.inferred_layer} 不在候选层 "
                f"{','.join(sorted(allowed))} 中"
            )
        ]
    }


def validate_metadata_quality(
    result: TableInspectResult,
) -> dict[str, list[str]]:
    """校验可写入模型 YAML 的关键语义元数据是否自洽。"""
    validation: dict[str, list[str]] = {}
    layer = str(result.inferred_layer or "").upper()
    table_type = str(result.table_type or "").lower()
    metric_names = _metric_names_from_items(
        result.atomic_metrics
        + result.derived_metrics
        + result.calculated_metrics
    )

    if layer == "DWS" and table_type == "fact":
        if not metric_names:
            validation["missing_metric_metadata"] = [
                "DWS fact必须至少返回一个指标字段"
            ]
        if not result.grain:
            validation["missing_grain_metadata"] = [
                "DWS fact必须尽量返回表级grain"
            ]

    if layer == "DIM" and table_type != "dimension":
        validation["invalid_dimension_table_type"] = [
            "DIM层模型的table_type必须为dimension"
        ]

    if layer == "DIM" or table_type == "dimension":
        has_primary_entity = any(
            str(entity.get("type") or "").strip().lower() == "primary"
            for entity in result.entities
            if isinstance(entity, dict)
        )
        if not has_primary_entity:
            validation["missing_dimension_entities"] = [
                "DIM/dimension模型必须尽量返回一个type=primary的entities项"
            ]

    return validation


def _metric_names_from_items(raw_metrics: Any) -> list[str]:
    if isinstance(raw_metrics, dict):
        iterable = []
        for group_metrics in raw_metrics.values():
            if isinstance(group_metrics, list):
                iterable.extend(group_metrics)
    elif isinstance(raw_metrics, list):
        iterable = raw_metrics
    else:
        iterable = []

    names = []
    for item in iterable:
        if isinstance(item, dict):
            name = str(item.get("name") or item.get("column") or "").strip()
        else:
            name = str(item or "").strip()
        if name and name not in names:
            names.append(name)
    return names


def _atomic_metric_tables_for_validation(
    result: TableInspectResult, ctx: TableContext
) -> dict[str, set[str]]:
    tables: dict[str, set[str]] = {}
    same_table_metrics = set(_metric_names_from_items(result.atomic_metrics))
    if same_table_metrics:
        tables[result.table_name] = same_table_metrics
    for table_name, groups in (ctx.upstream_metric_groups or {}).items():
        if not isinstance(groups, dict):
            continue
        names = set(_metric_names_from_items(groups.get("atomic_metrics")))
        if names:
            tables[str(table_name)] = names
    return tables


def _base_metric_candidate_tables(
    base_metric: str, atomic_metric_tables: dict[str, set[str]]
) -> list[str]:
    return sorted(
        table_name
        for table_name, metric_names in atomic_metric_tables.items()
        if base_metric in metric_names
    )


def enrich_metric_relationships(
    result: TableInspectResult, ctx: TableContext
) -> None:
    """补齐可唯一判断的派生指标 base_metric_table。"""
    atomic_metric_tables = _atomic_metric_tables_for_validation(result, ctx)
    for metric in result.derived_metrics:
        if str(metric.get("base_metric_table") or "").strip():
            continue
        base_metric = str(metric.get("base_metric") or "").strip()
        if not base_metric:
            continue
        candidates = _base_metric_candidate_tables(
            base_metric,
            atomic_metric_tables,
        )
        if len(candidates) == 1:
            metric["base_metric_table"] = candidates[0]


def validate_metric_relationships(
    result: TableInspectResult, ctx: TableContext
) -> dict[str, list[str]]:
    """校验派生指标是否显式指向已知原子指标。"""
    issues = {
        "missing_base_metrics": [],
        "missing_base_metric_tables": [],
        "invalid_base_metrics": [],
        "invalid_base_metric_tables": [],
        "ambiguous_base_metrics": [],
    }
    if not result.is_fact_table or not result.derived_metrics:
        return {}

    atomic_metric_tables = _atomic_metric_tables_for_validation(result, ctx)
    for metric in result.derived_metrics:
        metric_name = str(metric.get("name") or "").strip()
        base_metric = str(metric.get("base_metric") or "").strip()
        base_metric_table = str(metric.get("base_metric_table") or "").strip()
        if not metric_name:
            continue
        if not base_metric:
            issues["missing_base_metrics"].append(metric_name)
            continue

        if base_metric_table:
            table_metrics = atomic_metric_tables.get(base_metric_table)
            if table_metrics is None:
                issues["invalid_base_metric_tables"].append(
                    f"{metric_name}:{base_metric_table}"
                )
                continue
            if base_metric not in table_metrics:
                issues["invalid_base_metrics"].append(
                    f"{metric_name}:{base_metric_table}.{base_metric}"
                )
            continue

        candidates = _base_metric_candidate_tables(
            base_metric,
            atomic_metric_tables,
        )
        if len(candidates) > 1:
            issues["ambiguous_base_metrics"].append(
                f"{metric_name}:{base_metric}"
            )
        elif not candidates:
            issues["invalid_base_metrics"].append(
                f"{metric_name}:{base_metric}"
            )
        else:
            issues["missing_base_metric_tables"].append(metric_name)

    return {key: sorted(values) for key, values in issues.items() if values}


def _merge_validation(
    *validation_parts: dict[str, list[str]],
) -> dict[str, list[str]]:
    merged: dict[str, list[str]] = {}
    for validation in validation_parts:
        for key, values in (validation or {}).items():
            current = merged.setdefault(key, [])
            for value in values or []:
                text = str(value)
                if text not in current:
                    current.append(text)
    return {key: sorted(values) for key, values in merged.items()}


class TableInspector:
    def __init__(
        self,
        api_key: str,
        *,
        model: str = "deepseek-v4-flash",
        cache_file: Path = None,
        max_retries: int = 1,
        parallelism: int = 2,
        request_timeout: int = 180,
        base_url: str = "",
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = _normalize_api_base_url(
            base_url
            or os.environ.get("LLM_BASE_URL")
            or os.environ.get("DEEPSEEK_BASE_URL")
            or DEFAULT_API_BASE_URL
        )
        self.cache_file = cache_file
        self.max_retries = max(0, int(max_retries))
        self.parallelism = max(1, int(parallelism))
        self.request_timeout = max(1, int(request_timeout))
        self.cache = {}
        self._cache_lock = threading.RLock()
        self.progress_callback: Callable[[dict[str, Any]], None] | None = None
        self._load_cache()

    def _load_cache(self):
        with self._cache_lock:
            if self.cache_file and self.cache_file.exists():
                try:
                    self.cache = json.loads(
                        self.cache_file.read_text(encoding=TEXT_ENCODING)
                    )
                except Exception:
                    self.cache = {}

    def _save_cache(self):
        with self._cache_lock:
            if self.cache_file:
                self.cache_file.parent.mkdir(parents=True, exist_ok=True)
                self.cache_file.write_text(
                    json.dumps(self.cache, ensure_ascii=False, indent=2),
                    encoding=TEXT_ENCODING,
                )

    def _compute_hash(self, ctx: TableContext) -> str:
        # 缓存 hash 需要包含所有影响 LLM 判断的特征与 prompt schema 版本。
        content = (
            f"{PROMPT_VERSION}|{self.model}|{self.base_url}|"
            f"{ctx.table_name}|{ctx.layer}|{ctx.ddl}|"
            f"{ctx.etl_sql}|{ctx.upstream_tables}|{ctx.downstream_tables}|"
            f"{ctx.depth_from_ods}|{ctx.upstream_metric_groups}|"
            f"{ctx.column_lineage}|{ctx.declared_data_domain}|"
            f"{ctx.declared_business_area}|{ctx.business_domain_options}|"
            f"{ctx.business_semantics_options}|{ctx.project_context}|"
            f"{ctx.candidate_layers}"
        )
        return hashlib.sha256(content.encode(TEXT_ENCODING)).hexdigest()

    def _emit_progress(
        self,
        event: str,
        ctx: TableContext,
        *,
        progress_context: dict[str, Any] | None = None,
        **extra: Any,
    ) -> None:
        callback = self.progress_callback
        if not callback:
            return
        payload = {
            "event": event,
            "table": ctx.table_name,
            "layer": ctx.layer,
        }
        if progress_context:
            payload.update(progress_context)
        payload.update(extra)
        try:
            callback(payload)
        except Exception:
            return

    def _call_api(self, prompt: str) -> str:
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.api_key}",
            # Some OpenAI-compatible gateways reject urllib's default user agent.
            "User-Agent": "Mozilla/5.0",
            "Accept": "application/json",
        }
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
        }

        payload = json.dumps(data).encode(TEXT_ENCODING)
        errors: list[Exception] = []
        urls = _completion_urls(self.base_url)
        for index, url in enumerate(urls):
            req = urllib.request.Request(
                url,
                data=payload,
                headers=headers,
                method="POST",
            )
            try:
                with urllib.request.urlopen(
                    req, timeout=self.request_timeout
                ) as response:
                    return response.read().decode(TEXT_ENCODING)
            except urllib.error.HTTPError as e:
                body = e.read().decode(TEXT_ENCODING, errors="replace")
                errors.append(
                    RuntimeError(
                        f"HTTP {e.code}: {body[:500] or e.reason}"
                    )
                )
                if e.code not in {403, 404, 405, 501} or index == len(urls) - 1:
                    break
            except Exception as e:
                errors.append(e)
                break
        last_error = errors[-1] if errors else RuntimeError("unknown error")
        raise RuntimeError(f"LLM API 调用失败: {last_error}") from last_error

    def inspect(
        self,
        ctx: TableContext,
        *,
        progress_context: dict[str, Any] | None = None,
    ) -> TableInspectResult:
        current_hash = self._compute_hash(ctx)

        with self._cache_lock:
            cached_data = self.cache.get(ctx.table_name)
            if (
                isinstance(cached_data, dict)
                and cached_data.get("hash") == current_hash
            ):
                self._emit_progress(
                    "cache_hit", ctx, progress_context=progress_context
                )
                return dict_to_result(
                    cached_data.get("result", {}),
                    table_name=ctx.table_name,
                    declared_layer=ctx.layer,
                )

        ddl_columns = _extract_ddl_column_names(ctx.ddl)
        prompt = build_prompt(ctx)
        result = None
        for attempt in range(self.max_retries + 1):
            self._emit_progress(
                "api_call",
                ctx,
                progress_context=progress_context,
                attempt=attempt + 1,
                max_attempts=self.max_retries + 1,
            )
            try:
                resp_str = self._call_api(prompt)
                resp_json = json.loads(resp_str)
            except Exception as e:
                result = TableInspectResult(
                    table_name=ctx.table_name,
                    declared_layer=ctx.layer,
                    inferred_layer="OTHER",
                    table_type="other",
                    confidence=0.0,
                    reasoning_steps=[f"分类异常: {str(e)}"],
                    retry_count=attempt,
                )
                self._emit_progress(
                    "api_error",
                    ctx,
                    progress_context=progress_context,
                    attempt=attempt + 1,
                    max_attempts=self.max_retries + 1,
                    error=str(e),
                )
                if attempt >= self.max_retries:
                    break
                continue

            result = parse_response(ctx.table_name, resp_json, ctx.layer)
            result.retry_count = attempt
            enrich_metric_relationships(result, ctx)
            result.validation = _merge_validation(
                validate_columns(result, ddl_columns),
                validate_time_periods(result),
                validate_metric_expressions(result),
                validate_primary_entities(result),
                validate_candidate_layer(result, ctx.candidate_layers),
                validate_metadata_quality(result),
                validate_metric_relationships(result, ctx),
            )
            if result.status == "passed" or attempt >= self.max_retries:
                break
            self._emit_progress(
                "validation_retry",
                ctx,
                progress_context=progress_context,
                attempt=attempt + 1,
                max_attempts=self.max_retries + 1,
                status=result.status,
                validation=result.validation,
            )
            prompt = build_retry_prompt(ctx, result, ddl_columns)

        with self._cache_lock:
            self.cache[ctx.table_name] = {
                "hash": current_hash,
                "result": result_to_cache_dict(result),
            }
            self._save_cache()

        return result

    def inspect_batch(
        self, contexts: list[TableContext]
    ) -> list[TableInspectResult]:
        total = len(contexts)

        def inspect_safely(
            item: tuple[int, TableContext],
        ) -> TableInspectResult:
            index, ctx = item
            progress_context = {"index": index, "total": total}
            self._emit_progress(
                "start", ctx, progress_context=progress_context
            )
            try:
                result = self.inspect(ctx, progress_context=progress_context)
            except Exception as e:
                result = TableInspectResult(
                    table_name=ctx.table_name,
                    declared_layer=ctx.layer,
                    inferred_layer="OTHER",
                    table_type="other",
                    confidence=0.0,
                    reasoning_steps=[f"分类异常: {str(e)}"],
                )
                self._emit_progress(
                    "unexpected_error",
                    ctx,
                    progress_context=progress_context,
                    error=str(e),
                )
            self._emit_progress(
                "finish",
                ctx,
                progress_context=progress_context,
                status=result.status,
                retry_count=result.retry_count,
                atomic_metric_count=len(result.atomic_metrics),
                derived_metric_count=len(result.derived_metrics),
                calculated_metric_count=len(result.calculated_metrics),
            )
            return result

        if len(contexts) <= 1 or self.parallelism == 1:
            return [
                inspect_safely((index, ctx))
                for index, ctx in enumerate(contexts, start=1)
            ]

        max_workers = min(self.parallelism, len(contexts))
        indexed_contexts = list(enumerate(contexts, start=1))
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            return list(executor.map(inspect_safely, indexed_contexts))
