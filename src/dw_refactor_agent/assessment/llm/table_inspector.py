from __future__ import annotations

import hashlib
import json
import math
import re
import threading
import urllib.request
from concurrent.futures import FIRST_COMPLETED, ThreadPoolExecutor, wait
from dataclasses import dataclass, field
from http.client import HTTPException
from pathlib import Path
from typing import Any, Callable
from urllib.error import HTTPError
from urllib.parse import urlparse

from dw_refactor_agent.assessment.llm.context_builder import TableContext
from dw_refactor_agent.assessment.llm.inspection_cache_policy import (
    InspectionCachePolicy,
    InvalidInspectionCacheError,
)
from dw_refactor_agent.assessment.llm.inspection_contract import (
    validate_generate_inspection_contract,
)
from dw_refactor_agent.assessment.llm.inspection_issues import (
    LEGACY_VALIDATION_ISSUE_CODES,
    InspectionAuthenticationError,
    InspectionBoundaryError,
    InspectionConfigurationError,
    InspectionContentParseError,
    InspectionInternalError,
    InspectionIssue,
    InspectionRequestRejectedError,
    InspectionTransportError,
    IssueEvidence,
    ParsedInspectionCandidate,
    RawInspectionResponse,
    UnknownInspectionIssueError,
    is_legacy_validation_issue,
    issue_for_code,
    issues_from_validation,
    issues_to_dicts,
    sort_issues,
)
from dw_refactor_agent.assessment.project_facts.entity_metadata import (
    legacy_entity_from_entities,
    legacy_related_entities_from_entities,
    normalize_entities,
)
from dw_refactor_agent.assessment.project_facts.time_period import (
    is_canonical_time_period,
    normalize_time_period,
)
from dw_refactor_agent.config import TEXT_ENCODING

PROMPT_VERSION = "table-inspector-v47"
VALID_LAYERS = {"DWD", "DWS", "DIM", "OTHER"}
VALID_TABLE_TYPES = {"dimension", "fact", "bridge", "other"}
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
RESOLUTION_REINSPECTION_ERROR_KEY = "resolution_requires_reinspection"
METRIC_CONTEXT_REINSPECTION_ERROR_KEY = "metric_context_reinspection_failed"
METRIC_PROPAGATION_ERROR_KEY = "metric_propagation_not_converged"
DDL_COLUMNS_UNAVAILABLE_ERROR_KEY = "ddl_columns_unavailable"
AMBIGUOUS_MIN_MAX_WARNING_KEY = "ambiguous_min_max_aggregation"
VALIDATION_ERROR_KEYS = (
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
    "inconsistent_layer_table_types",
    "inconsistent_layer_sql",
    "inconsistent_upstream_metric_layers",
    "business_process_missing",
    "business_process_ambiguous",
    "composite_process_invalid",
    "bridge_entities_invalid",
    "bridge_grain_invalid",
    "bridge_semantics_invalid",
    "duplicate_entity_codes",
    "entity_key_missing",
    "grain_entity_unknown",
    "grain_column_missing",
    "dimension_primary_entity_invalid",
    DDL_COLUMNS_UNAVAILABLE_ERROR_KEY,
    RESOLUTION_REINSPECTION_ERROR_KEY,
    METRIC_CONTEXT_REINSPECTION_ERROR_KEY,
    METRIC_PROPAGATION_ERROR_KEY,
)
VALIDATION_WARNING_KEYS = (AMBIGUOUS_MIN_MAX_WARNING_KEY,)
ORCHESTRATION_VALIDATION_KEYS = frozenset(
    {
        METRIC_CONTEXT_REINSPECTION_ERROR_KEY,
        METRIC_PROPAGATION_ERROR_KEY,
        RESOLUTION_REINSPECTION_ERROR_KEY,
    }
)
DEFAULT_DEEPSEEK_CHAT_COMPLETIONS_URL = (
    "https://api.deepseek.com/chat/completions"
)
AUTHENTICATION_HTTP_STATUS_CODES = frozenset({401, 403})
RETRYABLE_HTTP_STATUS_CODES = frozenset({408, 409, 425, 429})
NON_METRIC_AGGREGATE_FUNCTIONS = {
    "ANY_VALUE",
    "ARBITRARY",
    "FIRST",
    "FIRST_VALUE",
    "LAST",
    "LAST_VALUE",
}
KNOWN_METRIC_AGGREGATE_FUNCTIONS = {
    "APPROX_COUNT_DISTINCT",
    "APPROX_DISTINCT",
    "ARRAY_AGG",
    "AVG",
    "BITMAP_UNION",
    "BITMAP_UNION_COUNT",
    "COUNT",
    "GROUP_CONCAT",
    "HLL_UNION",
    "HLL_UNION_AGG",
    "MEDIAN",
    "NDV",
    "QUANTILE_UNION",
    "SUM",
}
DEFAULT_MIN_CACHEABLE_CONFIDENCE = 0.5
MAX_CACHE_VARIANTS_PER_TABLE = 4


def normalize_chat_completions_url(base_url: str | None) -> str:
    """Normalize root API URLs to the chat completions endpoint."""
    value = str(base_url or "").strip().rstrip("/")
    if not value:
        return DEFAULT_DEEPSEEK_CHAT_COMPLETIONS_URL
    parsed = urlparse(value)
    if (
        parsed.scheme in {"http", "https"}
        and parsed.netloc == "api.deepseek.com"
        and parsed.path in {"", "/", "/v1"}
    ):
        return "https://api.deepseek.com/chat/completions"
    return value


def _empty_columns() -> dict[str, list[dict[str, Any]]]:
    return {group: [] for group in COLUMN_GROUPS}


def _valid_business_process(value: Any) -> str:
    if not isinstance(value, str):
        return ""
    text = value.strip()
    if not re.fullmatch(r"[A-Za-z][A-Za-z0-9_]*", text):
        return ""
    return text


def _valid_business_process_mode(value: Any) -> str:
    mode = str(value or "").strip().lower()
    return mode if mode == "composite" else ""


def _format_layered_tables(
    tables: list[str],
    layers: dict[str, str],
) -> str:
    if not tables:
        return "无"
    rendered = []
    for table in tables:
        layer = str(layers.get(table) or "").strip().upper()
        rendered.append(f"{table}({layer})" if layer else table)
    return ", ".join(rendered)


def _prompt_layer(ctx: TableContext) -> str:
    return ctx.layer if ctx.expose_layer_hints else "未提供"


def _prompt_table_layers(
    ctx: TableContext,
    layers: dict[str, str],
) -> dict[str, str]:
    return layers if ctx.expose_layer_hints else {}


def _prompt_depth_feature(ctx: TableContext) -> str:
    if not ctx.expose_layer_hints:
        return ""
    return f"- 距 ODS 最小跳数: {ctx.depth_from_ods}\n"


@dataclass
class TableInspectResult:
    table_name: str
    declared_layer: str
    inferred_layer: str  # "ODS" | "DWD" | "DWS" | "ADS" | "DIM" | "OTHER"
    table_type: str  # "dimension" | "fact" | "bridge" | "other"
    confidence: float
    reasoning_steps: list[str]
    business_process: str = ""
    business_process_mode: str = ""
    business_process_sources: list[str] = field(default_factory=list)
    business_process_conflicts: list[str] = field(default_factory=list)
    columns: dict[str, list[dict[str, Any]]] = field(
        default_factory=_empty_columns
    )
    validation: dict[str, list[str]] = field(default_factory=dict)
    issues: tuple[InspectionIssue, ...] = field(default_factory=tuple)
    raw_response: RawInspectionResponse | None = None
    parsed_candidate: ParsedInspectionCandidate | None = None
    retry_count: int = 0
    first_attempt_inferred_layer: str = ""
    inferred_data_domain: str = ""
    inferred_business_area: str = ""
    dimension_role: str = ""
    dimension_content_type: str = ""
    entities: list[dict[str, Any]] = field(default_factory=list)
    entity: dict[str, Any] = field(default_factory=dict)
    related_entities: list[dict[str, Any]] = field(default_factory=list)
    grain: dict[str, Any] = field(default_factory=dict)
    context_hash: str = ""
    catalog_snapshot_hash: str = ""
    asset_manifest_hash: str = ""
    reuse_source: str = ""
    resume_eligible: bool = True

    def __post_init__(self) -> None:
        self.confidence = _safe_float(self.confidence)
        self.business_process = _valid_business_process(self.business_process)
        self.business_process_mode = _valid_business_process_mode(
            self.business_process_mode
        )
        self.business_process_sources = list(
            dict.fromkeys(
                str(source).strip()
                for source in self.business_process_sources
                if str(source).strip()
            )
        )
        self.business_process_conflicts = list(
            dict.fromkeys(
                str(metric).strip()
                for metric in self.business_process_conflicts
                if str(metric).strip()
            )
        )
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
    def is_bridge_table(self) -> bool:
        return self.table_type == "bridge"

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
        unknown_keys = set(self.validation) - set(
            LEGACY_VALIDATION_ISSUE_CODES
        )
        if unknown_keys:
            raise UnknownInspectionIssueError(
                "unregistered inspection validation keys: "
                + ", ".join(sorted(unknown_keys))
            )
        if self.confidence <= 0:
            return "blocked"
        if any(self.validation.get(key) for key in VALIDATION_ERROR_KEYS):
            return "blocked"
        if any(self.validation.get(key) for key in VALIDATION_WARNING_KEYS):
            return "warning"
        return "passed"


def build_prompt(ctx: TableContext) -> str:
    prompt = f"""你是一位资深数据仓库架构师和指标治理专家。你的任务是根据给定的表结构、ETL 加工逻辑和血缘关系，完成一次统一巡检:
1. 客观推断这张表真实应该归属的数仓分层。
2. 判断它的物理表类型（维度表/事实表/关系桥/其他）。
3. 识别 entities、grain 元数据候选。
4. 如果推断层级是 DWD 或 DWS 且你判断它是事实表，则对字段分组识别原子指标、派生指标、衍生指标、维度字段和其他字段。

## 数仓分层判定标准
- ODS (贴源层): 直接同步业务库，通常不含复杂的转化逻辑，数据粒度与源库完全一致。
- DWD (明细宽表层): 对 ODS 进行数据清洗、维度退化(多表 JOIN 拉宽)，但目标行驱动查询必须保持事务明细粒度，不能通过聚合把多行压缩成目标公共分析粒度。
- DWS (汇总层): 当前模型把多行压缩到公共分析粒度，或明确发布上游已经治理的公共指标及其汇总粒度。DWS 判定依据是公共指标粒度，不是表名中的 summary/snapshot 等词。
- ADS (应用层): 面向最终报表或业务大屏的定制化数据，可能包含复杂的衍生指标。出度为 0 只能作为弱证据；如果血缘不完整、当前表位于中间层候选目录，或 ETL 显示其仍是公共明细/汇总资产，不得仅凭下游为空判为 ADS。
- DIM (公共维度表): 记录稳定实体或参考上下文的属性，供事实分析切片、解释或关联。下游 LEFT JOIN 是发布边界的确认信号，但血缘不完整或暂时没有下游时，并非成为 DIM 的必要条件。

## 表类型判定标准
- table_type 必须依据行粒度、键约束、聚合位置、时间字段和 JOIN 复用关系判断，不能仅依据表名、字段名或是否包含数值字段。
- fact: 每行表示可独立识别的事件、明细或周期状态，具有稳定行键、发生/观察时间和可汇总度量；聚合事实还应有明确公共粒度。
- dimension: 每行围绕稳定实体标识组织描述性属性，并作为查询或 JOIN 上下文被事实模型复用；它本身不承载事件度量。
- bridge: 每行只表达两个或多个业务实体之间的成员、归属、适用或多对多关系，本身没有独立业务事件、观察时间或可汇总度量。参与实体键共同构成行粒度，且不填写业务过程。
- other: 保持源行粒度的清洗、标准化或技术中间模型，尚未形成可复用维度发布边界，也不表达可度量事实。
- 对同一实体键跨时间保留多个版本时，结合版本键、有效期/观察时间以及输出字段职责判断：主要输出描述性属性的是 dimension，主要输出可汇总度量的是 fact；时间字段本身不能决定表类型。

## 中间层候选与边界层规则
- 当前巡检对象仅来自 DWD/DWS/DIM 可写模型候选；ODS 和 ADS 由资产目录边界固定，不参与中间层 LLM 裁决，也不得作为 inferred_layer 返回。
- 如果原始配置层级是 DWD、DWS 或 DIM，且没有明确的 ads 资产目录、应用报表命名或最终看板用途证据，请优先在 DWD/DWS/DIM 中选择。
- DWD: 输出行与输入明细保持同一粒度，转换主要是清洗、标准化、去重或逐行增强；目标行驱动查询没有把多行压缩为公共分析粒度，JOIN 聚合结果也没有作为公共业务指标发布。
- DWS: 目标行驱动查询通过聚合把多行压缩到公共分析粒度，或当前模型消费“上游指标分组”中已经处于公共分析粒度的指标并保持/再发布该粒度；必须返回 fact。JOIN 聚合子查询若按业务实体与时间粒度产生 COUNT/SUM/AVG 等指标，并把这些指标作为目标表的正式分析输出，也属于 DWS；若聚合只补充首末日期、名称、状态、分类等查询辅助属性，且主驱动行仍逐行保留，才不属于目标表聚合。
- DIM: 具有稳定实体标识和描述性属性，输出以描述性、分类或参考上下文属性为主，并且不表达业务事件或可汇总事实。下游 JOIN 可确认复用，但下游为空不能否定已成立的实体发布职责；生成新键本身不足以证明它是维度表。
- 当前 SQL 没有压缩主驱动行、且没有上游公共指标证据时，不得仅凭表名、日期字段、snapshot/summary 语义或源系统已物化的余额/汇总字段判为 DWS。继续根据输出行是明细事实、可复用实体还是技术中间结果，在 DWD/fact、DIM/dimension 和 DWD/other 之间判断。
- OTHER 不能作为 ODS 的替代返回值。ODS/ADS 边界已由资产目录固定；中间层候选若每行表达可识别的业务事件、状态、关系或快照事实，即使 ETL 只是近似贴源的清洗/标准化，也应在 DWD/DWS 中选择。OTHER/other 只用于不表达业务事实、公共指标或可复用实体的纯技术中间结果。
- 必须区分“内容围绕实体组织”和“已经到达维度发布边界”：单表逐行清洗、标准化、类型转换或标签衍生后的实体数据，如果下游才生成正式实体代理键并保留自然键，则当前表仍是 DWD/other；不能仅因当前表有稳定实体 ID 和描述性属性就提前判为 DIM。
- 下游生成代理键本身不是硬裁决；但若下游同时保留自然键、没有聚合，当前表又只做实体清洗/属性派生且不表达业务事件或可度量事实，这组证据共同确认下游才是正式维度发布边界，当前表必须返回 DWD/other，不得提前返回 DIM。若当前表承载事件或事实度量，仍应按事实语义判断。
- 若没有下游实体发布结构特征，稳定实体键 + 以描述性属性为主 + 无事件/度量语义，可以直接构成 DIM 发布边界；不得仅因当前 ETL 是单表逐行标准化或下游引用数为 0 就强制降为 DWD/other。
- 快照、版本、关系和数值字段本身都不是层级证据；必须结合目标行粒度、是否表达业务事件/公共指标、以及是否作为描述性上下文复用综合判断。
- 关系模型若只表达两个或多个实体之间的成员、归属、适用或多对多关系，且没有独立事件、观察时间或可汇总度量，应判为 DWD/bridge；若它表达可识别的业务事件或周期状态，则判为 DWD/fact；若主要用于解释、计算或匹配的参考配置，则判为 DIM/dimension。不得仅依赖字段词或是否有日期硬裁决。
- 若当前表把独立上游指标源 JOIN 到目标分析粒度并继续发布，应保持 DWS/fact；但直接透传单一明细来源并保持其行粒度时，不能仅因字段已被识别为指标就升级为 DWS。
- 下游引用数为 0 只能作为边界层弱证据，不能覆盖粒度、聚合和资产目录证据。

## 维表分类标准
当 table_type=dimension 或 inferred_layer=DIM 时，必须额外判断维表内容形态和维表建设角色。
- dimension_content_type=INFO: 属性信息维表。描述实体基础属性、业务属性、状态、日期、名称、说明等。
- dimension_content_type=TAG: 标签维表。描述规则、指标、模型或统计加工形成的标签、分层、评分、画像、偏好、风险等级等。
- dimension_content_type=TREE: 树形维表。描述父子节点、层级、路径、上下级归属、祖先节点、叶子节点，支持上卷和下钻。
- dimension_role=BASE: 主维度。描述实体最核心、最标准、公共复用的身份和基础信息。
- dimension_role=ADDT: 辅维度。描述实体补充信息、扩展属性、关系信息、场景化属性或低频属性。
若当前表不是维度表，dimension_role 和 dimension_content_type 都返回空字符串。

## 业务过程与语义主题边界
- 顶层 business_process 只适用于事实表或汇总事实表，用来描述整张表发生了什么业务事件/活动；判断依据应是事件动作、事实行、度量字段、时间粒度和可汇总口径，而不是表名里出现的业务名词。bridge/dimension/other 必须返回空字符串。
- 必须先依据前述分层和表类型规则独立确定 table_type，再填写 business_process；是否能填写业务过程不能反过来作为判成 fact 的证据。
- 只要已经独立确定 table_type=fact，就必须判断顶层 business_process。即使表没有指标字段，只要每行能表达明确的事件发生、业务参与关系、状态变化或周期观察事实，也应根据行级业务事实填写唯一的业务过程 code。
- 稳定实体档案、描述属性、主数据或逐行实体清洗，即使包含状态、日期和外键，也不能为了填写 business_process 而改判 fact；它们仍按既有证据判断为 dimension/other，并返回空字符串。
- 如果多个过程都成立且无法确定唯一主过程，顶层 business_process 返回空字符串；不得为了通过校验而任选一个。bridge/dimension/other 的顶层 business_process 必须返回空字符串。
- dimension 表不得为了填充业务过程而生成“实体主语 + 管理/运营”式过程名；若表只表达管理/运营/主数据/资料维护/属性集合，它们更可能是语义主题、业务主题或实体管理域。
- semantic_subject 表示维度/实体属性表的语义主题，通常对应维表主实体编码；它不是业务过程，也不应被写入指标字段的 business_process。
- 表名或描述中含有 MANAGEMENT、OPERATION、PROFILE、MASTER、INFO 等模式时，必须先检查是否存在可度量业务事件；没有事件事实和指标时，优先视为语义主题/业务主题，不要归为严格的业务过程。
- 字段级 business_process 若需要填写，应是可代码化的大写下划线短语，表达“动作/事件 + 业务结果或业务对象”的过程；不能仅由实体主语、管理/运营词或表主题词组成。字段级过程与顶层过程共同作为一致性证据，不能用顶层字段掩盖指标属于多个过程的歧义。
- 如果提供了已确认业务语义目录，business_process 和 entities[].code 应优先复用目录中的 code；若没有合适 code，可以返回新的大写下划线候选，但必须由当前表的事件事实、指标口径或主实体证据支撑。
- 本次巡检 JSON 不返回 semantic_subject 顶层字段；这条规则用于避免把维表主题误填到指标字段的 business_process。catalog 初始化或 models 回写时可将 dimension 表主实体转为 semantic_subject。

## 指标字段分组标准
- atomic_metrics: 基于某一业务过程下不可再拆分的基础指标口径，通常由业务过程、度量对象和标准统计方式构成。对事件标识或实体标识字段做 COUNT/COUNT DISTINCT 生成基础计数口径时，应归 atomic_metrics；不包含比率、分数、多个度量组合、同一明细行内多个基础要素的算术组合、结果性明细度量、复杂 CASE/窗口函数/模型计算等二次计算。字段是否为原子指标不能只看 ETL 是否直接透传，必须结合字段语义和业务定义判断。business_process 仅当当前表是 fact/DWD fact/DWS 汇总事实且字段是指标时填写；dimension/属性字段返回空字符串。尽量填写 business_process/action/measure。
- derived_metrics: 放度量型派生指标，即一个已存在的原子指标 + 多个修饰词(可选) + 时间周期/统计粒度/限定条件。它本质上仍是对原子指标统计范围的限定，没有改变指标计算逻辑。DWS 汇总表中，如果字段是对上游已存在的 atomic_metrics 做 SUM/AVG/MIN/MAX 等标准聚合，并叠加维度、周期或限定条件，通常应归 derived_metrics，而不是 atomic_metrics。尽量填写 base_metric/modifiers/time_period/expression。
- calculated_metrics: 只放度量型衍生指标，即基于一个或多个已有指标，通过公式、规则、模型或二次计算得到的新指标，通常产生新的业务含义。包括比率、分数、差值、绝对值、风险等级、窗口函数、复杂 CASE 规则、多字段组合计算、同一明细行内多个基础要素组合后的结果度量等。即使字段从上游直接透传或上游已经预先算好，只要字段注释、字段级血缘或业务语义表明它是已物化的结果性度量，而不是独立观测到的基础计量，也应按 calculated_metrics 判断。DWS 汇总表中，如果字段是对上游 calculated_metrics 再聚合，也应归 calculated_metrics。尽量填写 expression/derived_from。
- dimensions: 主键、外键、日期、时间、状态、标签、枚举、布尔标志、退化维度、实体属性，以及用于切片、过滤、分组或公式输入但自身不可独立汇总的字段。
- others: 审计字段、技术字段、无法判断字段。
- DWD 事实表新增的治理口径原则上只能是 atomic_metrics；derived_metrics 和 calculated_metrics 属于 DWD 违规风险。但源业务事实中已经物化的结果字段不应改变表的结构分层：仍按 DWD/fact 判断并如实分类，由违规报告提示治理问题，不能为了回避违规返回 OTHER。
- DWS 事实表通常承载 derived_metrics；不要因为 DWS 表包含派生指标而判为违规。
- COUNT(*) 或 COUNT(事件键)直接形成当前目标粒度的基础计数时，将该输出字段识别为当前表的 atomic metric；条件 COUNT/SUM 也必须依据真实字段血缘描述计算逻辑。不得为了填写 base_metric 而虚构上游不存在的 count、amount、debit、credit 等语义指标名；只有上游真实字段或“上游指标分组”中已治理指标才能作为 base_metric。

## 度量可加性约束
- atomic_metrics 必须是可被独立观测、可计数或可按事实粒度直接汇总形成业务总量的基础口径。
- 只用于描述、切片或作为其他公式输入且自身不可独立汇总的字段，不能作为 atomic_metrics。
- 对属性字段做补值、回填、格式标准化或缺失值兜底，不会自动产生新的 calculated_metrics；只有字段本身形成新的业务结果口径时才按计算指标判断。
- 已物化的明细行结果度量即使来自上游直接透传，也不能作为 atomic_metrics；如果它表示当前事实行的业务结果，应归 calculated_metrics。
- 判断一个字段是否为 atomic_metrics 时，直接透传优先级低于可加性、字段注释、字段级血缘和业务语义。

## DWS 指标分类优先级
1. 对事件标识或实体标识字段做 COUNT/COUNT DISTINCT 生成基础计数指标时，优先归 atomic_metrics；分组维度和统计日期只表达当前汇总表粒度，不应单独导致它变成 derived_metrics。
2. 对上游 atomic_metrics 做 SUM/AVG/MIN/MAX 等聚合，并叠加维度、周期或限定条件时，归 derived_metrics。
3. 对上游 calculated_metrics 做聚合，或当前字段表达式包含多个度量组合时，归 calculated_metrics。
4. 判断上游字段类型时，优先参考“上游指标分组”；如果没有上游指标分组，再结合字段角色、注释、ETL 表达式和业务语义判断，不要套用字段名示例。
5. 对字段做分组时，优先使用字段级血缘表达式判断来源和计算关系；直接透传只能说明当前 ETL 没有再次计算，不能否定字段自身已经是结果性度量。

## 指标 expression 与 grain 边界
- metric.expression 只填写指标计算公式，例如 SUM(metric_a)、COUNT(DISTINCT entity_key)、SUM(metric_a - metric_b)。
- 不要在 metric.expression 中写 GROUP BY；不要在 metric.expression 中写“按...分组”、"by ..." 等粒度说明。
- 聚合粒度由表级 grain 表达；grain.entities 和 grain.time_column 应与 SQL GROUP BY 的业务粒度对齐。
- 如果 SQL 存在 GROUP BY，只从目标指标字段自身的 SELECT 表达式提取 metric.expression；GROUP BY 字段、时间字段、实体字段和中文粒度说明都不要写入 metric.expression。
- 输出前逐项检查所有 metric.expression：不得包含 GROUP BY、分组字段列表、时间粒度字段、实体粒度字段或中文粒度描述；若包含，应删除这些粒度片段，只保留指标计算公式。

## entities、grain 元数据识别
- entities 表示当前模型中参与语义关联的实体键，借鉴 dbt Semantic Layer entity。每个实体返回 code、type 和 key_columns。
- type 可取 primary、unique、foreign、natural。primary 表示当前表主实体键；unique 表示当前表内唯一但不是主实体；foreign 表示当前表引用其他实体的键；natural 表示拉链/快照表中标识业务实体但单独不唯一的自然键。
- 维度型/实体型表应至少返回一个 type=primary 的主实体；如果当前表承载上级、归属或层级实体，则用 type=foreign 并带 relationship。
- DWD fact 应优先识别能唯一标识当前事实行的主实体并返回 type=primary；复合业务键可以完整写入 key_columns，不要因为主键不是单列就放弃 primary。
- DWD fact 中仅作为分析上下文被引用的实体应返回 type=foreign。
- DWS 汇总事实表中的实体通常为 type=foreign，key_columns 是当前表中表示该实体的字段名；DWS 的行粒度由 grain 描述。
- grain 主要适用于 DWS 汇总事实表。若当前表是 DWS fact，应返回粒度实体 grain.entities、时间字段 time_column 和时间周期 time_period；DWD fact 只有在没有清晰 primary entity 但能由业务键/日期明确行粒度时才返回 grain；其他表 grain 返回空对象。
- grain.entities 必须引用当前返回的 entities[].code；它应来自粒度 key 对应的主要业务实体，不要把时间字段、状态、品牌、父级属性等普通维度属性放入 grain.entities。
- grain.entities 应返回完整的粒度实体集合；若粒度涉及多个实体，不要为了贴合 TABLE_DWS 命名段而裁剪 entities。
- time_period 只允许 D/W/M/Q/Y/S，含义分别为日/周/月/季/年/快照；不得返回中文、英文单词或 1d/1m 等窗口写法，无法判断时返回空字符串。
- 不要返回 grain.keys；粒度字段由 grain.entities 引用的 entities[].key_columns 加上 time_column 推导。
- 如果无法高置信判断 entities 或 grain，对应数组或对象返回空数组/空对象，不要编造字段或实体编码。

## 表级特征信息
- 原始表名: {ctx.table_name}
- 原始配置层级: {_prompt_layer(ctx)}
- 原始配置数据域: {ctx.declared_data_domain or "未配置"}
- 原始配置业务板块: {ctx.declared_business_area or "未配置"}
- 下游被引用次数: {len(ctx.downstream_tables)}
{_prompt_depth_feature(ctx)}

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
        prompt += """## 数据域与业务板块字典
未提供数据域与业务板块字典，本轮不进行数据域或业务板块发现:
- 数据域只适用于 DWD 层。当前表若不是 DWD，inferred_data_domain 必须返回空字符串。
- 业务板块只适用于 DWD 和 DWS 层。当前表若不是 DWD/DWS，inferred_business_area 必须返回空字符串。
- 未提供已确认字典时，inferred_data_domain 和 inferred_business_area 都必须返回空字符串。

"""
    if ctx.business_semantics_options:
        prompt += f"""## 已确认业务语义目录
请把下列目录作为人工确认过的治理输入使用。
- 事实表/汇总事实表的顶层 business_process 和指标字段若能匹配某个业务过程，必须优先复用目录中的 code。
- 维度表的 entities[].code 若能匹配某个语义主题，必须优先复用目录中的 code。
- 若没有合适 code，可以返回新的大写下划线候选；不要为了贴合目录而把维度主题填成业务过程。

可选目录:
{json.dumps(ctx.business_semantics_options, ensure_ascii=False, indent=2)}

"""
    if ctx.etl_sql:
        prompt += f"## ETL 加工逻辑\n{ctx.etl_sql}\n\n"

    prompt += f"""## 血缘关系
上游表: {_format_layered_tables(ctx.upstream_tables, _prompt_table_layers(ctx, ctx.upstream_table_layers))}
下游表: {_format_layered_tables(ctx.downstream_tables, _prompt_table_layers(ctx, ctx.downstream_table_layers))}

"""
    if ctx.downstream_entity_publication_features:
        prompt += f"""## 下游实体发布结构特征
以下内容仅由下游 SQL 结构提取，不包含下游层级标签。generated_key_columns 表示下游生成的新键，natural_key_aliases 表示下游显式保留的自然键，added_version_control_columns 表示下游新增的版本控制字段。请结合当前表是否只是逐行清洗来判断发布边界，不要仅凭表名判断。
{json.dumps(ctx.downstream_entity_publication_features, ensure_ascii=False, indent=2)}

"""

    prompt += f"""## 字段级血缘
{json.dumps(ctx.column_lineage, ensure_ascii=False, indent=2) if ctx.column_lineage else "无"}

## 上游指标分组
{json.dumps(ctx.upstream_metric_groups, ensure_ascii=False, indent=2) if ctx.upstream_metric_groups else "无"}

## 思考步骤
1. 从键、字段血缘和 ETL 判断输入与输出行粒度，检查所有查询阶段是否发生多行压缩或聚合；对 JOIN 聚合先区分“发布业务指标”和“补充查询属性”。
2. 判断每行是否表达业务事件、周期状态或参与/成员/责任/归属关系；关系桥不要求必须有日期或状态变化。再检查它是否实际只是决定计价、计算、入账、分类或解释方式的参数配置映射，后者才归参考维度。
3. 检查实体版本语义：批次参数加最新版本筛选不能自动构成周期事实，主要发布实体描述属性时优先判断维度职责。
4. 结合上下游 JOIN 与复用关系确认当前表在链路中的发布职责；生成新键或出现日期字段都只能作为辅助证据。
5. 若下游实体发布结构特征显示下游才生成代理键并保留自然键，检查当前表是否只是实体逐行清洗；满足时当前表应为 DWD/other，而下游才是实体发布边界。
6. 将下游引用数作为弱证据，并结合资产目录、粒度、聚合和用途判断边界层。
7. 检查组合一致性：DIM 必须对应 dimension，dimension 必须对应 DIM，DWS 必须对应 fact；bridge 必须对应 DWD；DWD 可对应 fact、bridge 或 other。
8. 如果 inferred_layer 是 DWD 或 DWS 且表类型为 fact，再按字段语义、DDL 注释、ETL 表达式和业务过程分组；COUNT 和条件聚合必须使用真实字段血缘，不得虚构上游基础指标。

请严格返回 JSON 格式数据，只允许返回下方 JSON schema 中列出的顶层字段: inferred_layer、table_type、business_process、inferred_data_domain、inferred_business_area、dimension_role、dimension_content_type、entities、grain、confidence、reasoning_steps、columns。
不要返回 Markdown，不要返回额外解释，不要新增任何字段。
如果不需要做字段分组，columns 下五个数组都返回空数组。

{{
  "inferred_layer": "DWD|DWS|DIM|OTHER",
  "table_type": "dimension|fact|bridge|other",
  "business_process": "事实表唯一的表级业务过程 code；不适用、无法判断唯一过程时为空字符串",
  "inferred_data_domain": "已确认数据域编号；未提供字典、不适用或不确定时为空字符串",
  "inferred_business_area": "已确认业务板块简写；未提供字典、不适用或不确定时为空字符串",
  "dimension_role": "BASE|ADDT",
  "dimension_content_type": "INFO|TAG|TREE",
  "entities": [
    {{
      "code": "实体编码，如 ENTITY_A；不适用或无法判断时返回空数组",
      "type": "primary|unique|foreign|natural",
      "name": "实体名称，如 实体A；无法判断则为空字符串",
      "key_columns": ["当前表中表示该实体的字段名"],
      "relationship": {{
        "type": "many_to_one|one_to_many|one_to_one|hierarchy",
        "from_entity": "当前表主实体编码，如 ENTITY_A；不适用则为空字符串"
      }}
    }}
  ],
  "grain": {{
    "entities": ["粒度实体编码，如 ENTITY_A"],
    "time_column": "时间粒度字段名，如 period_key；无则为空字符串",
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
- inconsistent_layer_table_types 表示层级与物理表职责组合矛盾；DIM 必须返回 dimension，dimension 必须返回 DIM，DWS 必须返回 fact，bridge 必须返回 DWD，DWD 只能返回 fact、bridge 或 other。
- OTHER/fact 不是合法的中间层组合：ODS/ADS 边界已经固定，贴源清洗后的业务事件、关系、状态或快照事实应在 DWD/DWS 中选择；不要用 OTHER 代替 ODS。
- inconsistent_layer_sql 表示 DWD 候选的目标行驱动查询存在 GROUP BY 并压缩目标粒度；必须根据公共聚合粒度重新判断。仅在 JOIN 辅助子查询中聚合以补充日期/属性、主驱动行仍逐行保留时，可以继续返回 DWD。
- ambiguous_min_max_aggregation 表示代码无法仅凭同名 MIN/MAX 判断它是技术选值还是业务汇总；如果输出是业务统计结果，应归入指标字段并返回 DWS，如果只是保留实体最新/最早技术状态，可继续返回 DWD，并在字段 reason 中说明技术选值依据。
- inconsistent_upstream_metric_layers 表示 DWD 候选把独立上游指标源中的公共指标 JOIN 到目标分析粒度并继续发布；应返回 DWS/fact 并保留正确的上游指标依赖关系。单一明细来源的逐行透传不属于此错误。
- business_process_missing / business_process_ambiguous 表示 fact 的表级和字段级业务过程没有共同形成唯一一致 code；字段级 process 为空时可继承唯一表级 code，非空时必须与表级 code 一致。真实多过程且无法确定主过程时保持空；系统仅在 DWS 有至少两个上游真实贡献指标时确定性记录 composite 来源，否则继续安全阻断。
- bridge_entities_invalid / bridge_grain_invalid 表示关系桥必须包含至少两个不同参与实体，且 grain.entities 必须完整覆盖这些实体；bridge_semantics_invalid 表示关系桥错误携带了 business_process 或指标，必须清空业务过程和三个指标分组。
- duplicate_entity_codes 表示多个实体复用了同一 code；同一业务实体承担不同角色时必须使用可区分的角色 code，不能由 writer 猜测合并或改名。
- entity_key_missing 表示 entity 缺少 key_columns 或 key 不在 DDL 中；grain_entity_unknown / grain_column_missing 表示 grain 引用了未声明实体或不存在字段，必须只使用本次 JSON 与 DDL 中真实存在的值。
- dimension_primary_entity_invalid 表示 dimension 必须返回且仅返回一个 type=primary 的主实体。
- invalid_base_metrics / invalid_base_metric_tables 中的 base_metric 必须是字段血缘或上游指标分组中真实存在的原子指标列名，不能编造语义标签。COUNT(*) 或 COUNT(事件键)形成的基础计数应归 atomic_metrics；无法验证上游原子指标时，不要虚构 base_metric/base_metric_table。
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


def _safe_float(value: Any) -> float:
    try:
        confidence = float(value)
    except (TypeError, ValueError):
        return 0.0
    if not math.isfinite(confidence) or not 0.0 <= confidence <= 1.0:
        return 0.0
    return confidence


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


def _response_content(response: dict[str, Any]) -> str:
    if not isinstance(response, dict):
        raise InspectionContentParseError(
            "API response envelope must be a JSON object"
        )
    choices = response.get("choices")
    if not isinstance(choices, list) or not choices:
        raise InspectionContentParseError(
            "API response envelope has no choices"
        )
    first_choice = choices[0]
    if not isinstance(first_choice, dict):
        raise InspectionContentParseError(
            "API response choice must be an object"
        )
    message = first_choice.get("message")
    if not isinstance(message, dict):
        raise InspectionContentParseError(
            "API response choice has no message object"
        )
    content = message.get("content")
    if not isinstance(content, str) or not content.strip():
        raise InspectionContentParseError(
            "API response message content must be a non-empty string"
        )
    return _strip_markdown_json(content)


def _parse_failure_result(
    *,
    table_name: str,
    declared_layer: str,
    raw_response: RawInspectionResponse,
    error: InspectionContentParseError,
) -> TableInspectResult:
    return TableInspectResult(
        table_name=table_name,
        declared_layer=str(declared_layer or ""),
        inferred_layer="OTHER",
        table_type="other",
        confidence=0.0,
        reasoning_steps=[f"JSON 解析失败: {error}"],
        issues=(error.to_issue(table_name),),
        raw_response=raw_response,
    )


def parse_response(
    table_name: str,
    response: dict,
    declared_layer: str = "",
    *,
    raw_response: RawInspectionResponse | None = None,
) -> TableInspectResult:
    if raw_response is None:
        body = json.dumps(
            response,
            ensure_ascii=False,
            separators=(",", ":"),
            default=str,
        )
        raw_response = RawInspectionResponse.create(
            table_name=table_name,
            model="",
            endpoint="",
            context_hash="",
            body=body,
        )
    try:
        content = _response_content(response)
        data = json.loads(content)
        if not isinstance(data, dict):
            raise InspectionContentParseError(
                "inspection candidate must be a JSON object"
            )
        try:
            parsed_candidate = ParsedInspectionCandidate.create(
                table_name=table_name,
                raw_response_hash=raw_response.content_hash,
                payload=data,
            )
        except (TypeError, ValueError) as error:
            raise InspectionContentParseError(
                f"inspection candidate is not losslessly serializable: {error}"
            ) from error
    except json.JSONDecodeError as error:
        parse_error = InspectionContentParseError(str(error))
        parse_error.__cause__ = error
        return _parse_failure_result(
            table_name=table_name,
            declared_layer=declared_layer,
            raw_response=raw_response,
            error=parse_error,
        )
    except InspectionContentParseError as error:
        return _parse_failure_result(
            table_name=table_name,
            declared_layer=declared_layer,
            raw_response=raw_response,
            error=error,
        )

    return TableInspectResult(
        table_name=table_name,
        declared_layer=str(declared_layer or ""),
        inferred_layer=_valid_layer(data.get("inferred_layer")),
        table_type=_valid_table_type(data.get("table_type")),
        business_process=_valid_business_process(data.get("business_process")),
        confidence=_safe_float(data.get("confidence")),
        reasoning_steps=_safe_list(data.get("reasoning_steps")),
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
        raw_response=raw_response,
        parsed_candidate=parsed_candidate,
    )


def synchronize_result_issues(
    result: TableInspectResult,
) -> tuple[InspectionIssue, ...]:
    """Rebuild typed issues from the current compatibility validation view."""
    typed_issues = [
        issue
        for issue in result.issues
        if not is_legacy_validation_issue(issue)
    ]
    typed_issues.extend(issues_from_validation(result))
    if (
        result.confidence <= 0
        and result.parsed_candidate is not None
        and not any(
            issue.code
            in {
                "inspection_transport_failed",
                "inspection_content_parse_failed",
            }
            for issue in typed_issues
        )
    ):
        typed_issues.append(
            issue_for_code(
                "inspection_low_confidence",
                table=result.table_name,
                path="confidence",
                items=(result.confidence,),
            )
        )
    result.issues = sort_issues(typed_issues)
    return result.issues


def result_to_dict(result: TableInspectResult) -> dict[str, Any]:
    current_issues = synchronize_result_issues(result)
    return {
        "table_name": result.table_name,
        "declared_layer": result.declared_layer,
        "inferred_layer": result.inferred_layer,
        "table_type": result.table_type,
        "business_process": result.business_process,
        "business_process_mode": result.business_process_mode,
        "business_process_sources": result.business_process_sources,
        "business_process_conflicts": result.business_process_conflicts,
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
        "issues": issues_to_dicts(current_issues),
        "raw_response": (
            result.raw_response.to_dict()
            if result.raw_response is not None
            else None
        ),
        "parsed_candidate": (
            result.parsed_candidate.to_dict()
            if result.parsed_candidate is not None
            else None
        ),
        "status": result.status,
        "retry_count": result.retry_count,
        "first_attempt_inferred_layer": result.first_attempt_inferred_layer,
        "is_violating_declared_layer": result.is_violating_declared_layer,
    }


CACHE_RESULT_FIELDS = frozenset(
    {
        "cache_policy",
        "table_name",
        "declared_layer",
        "inferred_layer",
        "table_type",
        "business_process",
        "business_process_mode",
        "business_process_sources",
        "business_process_conflicts",
        "inferred_data_domain",
        "inferred_business_area",
        "dimension_role",
        "dimension_content_type",
        "confidence",
        "reasoning_steps",
        "columns",
        "entities",
        "entity",
        "related_entities",
        "grain",
        "validation",
        "issues",
        "raw_response",
        "parsed_candidate",
        "retry_count",
        "first_attempt_inferred_layer",
        "context_hash",
        "catalog_snapshot_hash",
        "asset_manifest_hash",
        "resume_eligible",
    }
)


def result_to_cache_dict(result: TableInspectResult) -> dict[str, Any]:
    """仅保存恢复巡检结果所需字段，派生字段由读取后重新计算。"""
    current_issues = synchronize_result_issues(result)
    return {
        "cache_policy": InspectionCachePolicy(
            context_hash=result.context_hash,
            catalog_snapshot_hash=result.catalog_snapshot_hash,
            asset_manifest_hash=result.asset_manifest_hash,
        ).to_dict(),
        "table_name": result.table_name,
        "declared_layer": result.declared_layer,
        "inferred_layer": result.inferred_layer,
        "table_type": result.table_type,
        "business_process": result.business_process,
        "business_process_mode": result.business_process_mode,
        "business_process_sources": result.business_process_sources,
        "business_process_conflicts": result.business_process_conflicts,
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
        "issues": issues_to_dicts(current_issues),
        "raw_response": (
            result.raw_response.to_dict()
            if result.raw_response is not None
            else None
        ),
        "parsed_candidate": (
            result.parsed_candidate.to_dict()
            if result.parsed_candidate is not None
            else None
        ),
        "retry_count": result.retry_count,
        "first_attempt_inferred_layer": result.first_attempt_inferred_layer,
        "context_hash": result.context_hash,
        "catalog_snapshot_hash": result.catalog_snapshot_hash,
        "asset_manifest_hash": result.asset_manifest_hash,
        "resume_eligible": result.resume_eligible,
    }


def cache_result_digest(result_data: dict[str, Any]) -> str:
    content = json.dumps(
        result_data,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    return hashlib.sha256(content.encode(TEXT_ENCODING)).hexdigest()


def dict_to_result(
    data: dict[str, Any], *, table_name: str = "", declared_layer: str = ""
) -> TableInspectResult:
    if "cache_policy" in data and set(data) != CACHE_RESULT_FIELDS:
        raise InvalidInspectionCacheError(
            "inspection cache result fields are incomplete or unknown"
        )
    raw_issues = data.get("issues") or []
    if not isinstance(raw_issues, list):
        raise ValueError("inspection result issues must be a list")
    raw_response_data = data.get("raw_response")
    parsed_candidate_data = data.get("parsed_candidate")
    return TableInspectResult(
        table_name=str(data.get("table_name") or table_name),
        declared_layer=str(data.get("declared_layer") or declared_layer),
        inferred_layer=_valid_layer(data.get("inferred_layer")),
        table_type=_valid_table_type(data.get("table_type")),
        business_process=_valid_business_process(data.get("business_process")),
        business_process_mode=_valid_business_process_mode(
            data.get("business_process_mode")
        ),
        business_process_sources=_safe_list(
            data.get("business_process_sources")
        ),
        business_process_conflicts=_safe_list(
            data.get("business_process_conflicts")
        ),
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
        issues=tuple(InspectionIssue.from_dict(issue) for issue in raw_issues),
        raw_response=(
            RawInspectionResponse.from_dict(raw_response_data)
            if raw_response_data is not None
            else None
        ),
        parsed_candidate=(
            ParsedInspectionCandidate.from_dict(parsed_candidate_data)
            if parsed_candidate_data is not None
            else None
        ),
        retry_count=int(data.get("retry_count", 0) or 0),
        first_attempt_inferred_layer=_valid_layer(
            data.get("first_attempt_inferred_layer")
            or data.get("inferred_layer")
        ),
        inferred_data_domain=_safe_str(data.get("inferred_data_domain")),
        inferred_business_area=_safe_str(
            data.get("inferred_business_area")
        ).upper(),
        dimension_role=_valid_dimension_role(data.get("dimension_role")),
        dimension_content_type=_valid_dimension_content_type(
            data.get("dimension_content_type")
        ),
        context_hash=str(data.get("context_hash") or ""),
        catalog_snapshot_hash=str(data.get("catalog_snapshot_hash") or ""),
        asset_manifest_hash=str(data.get("asset_manifest_hash") or ""),
        resume_eligible=bool(data.get("resume_eligible", True)),
    )


def _normalize_validation(value: Any) -> dict[str, list[str]]:
    if not isinstance(value, dict):
        return {}
    unknown_keys = set(value) - set(LEGACY_VALIDATION_ISSUE_CODES)
    if unknown_keys:
        raise UnknownInspectionIssueError(
            "unregistered inspection validation keys: "
            + ", ".join(sorted(str(key) for key in unknown_keys))
        )
    normalized = {}
    for key, raw_items in value.items():
        if not isinstance(raw_items, list):
            raise ValueError(f"inspection validation {key!r} must be a list")
        normalized[str(key)] = [str(item) for item in raw_items]
    return normalized


def _extract_ddl_column_names(ddl: str) -> set[str]:
    """从 DDL 中解析字段名，用于校验 LLM 字段分组结果。"""
    if not ddl.strip():
        return set()
    try:
        import sqlglot
        from sqlglot import exp
        from sqlglot.errors import ErrorLevel

        from dw_refactor_agent.sql.doris import (
            normalize_create_table_for_sqlglot,
        )

        columns = set()
        normalized_ddl = normalize_create_table_for_sqlglot(ddl)
        for stmt in sqlglot.parse(
            normalized_ddl,
            dialect="doris",
            error_level=ErrorLevel.IGNORE,
        ):
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
        return {
            DDL_COLUMNS_UNAVAILABLE_ERROR_KEY: [
                "无法从DDL建立字段集合，禁止覆盖指标分组"
            ]
        }

    grouped_names = []
    for group in COLUMN_GROUPS:
        for item in result.columns.get(group, []):
            grouped_names.append(str(item.get("name") or ""))

    seen = set()
    duplicates = set()
    for name in grouped_names:
        if not name:
            continue
        canonical_name = _canonical_column_name(name)
        if canonical_name in seen:
            duplicates.add(name)
        seen.add(canonical_name)

    returned_by_name = {
        _canonical_column_name(name): name for name in grouped_names if name
    }
    ddl_by_name = {
        _canonical_column_name(name): name for name in ddl_columns if name
    }
    validation = {
        "unknown_columns": sorted(
            returned_by_name[name]
            for name in returned_by_name.keys() - ddl_by_name.keys()
        ),
        "duplicate_columns": sorted(duplicates),
        "missing_columns": [],
    }
    inferred_layer = str(result.inferred_layer or "").upper()
    if inferred_layer in METRIC_GROUPING_LAYERS and result.is_fact_table:
        validation["missing_columns"] = sorted(
            ddl_by_name[name]
            for name in ddl_by_name.keys() - returned_by_name.keys()
        )
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
    if result.inferred_layer != "DWD" or not result.is_fact_table:
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


def validate_layer_table_type_consistency(
    result: TableInspectResult,
) -> dict[str, list[str]]:
    """校验层级和物理表职责组合，避免 writer 再做内容改写。"""
    layer = str(result.inferred_layer or "").upper()
    table_type = str(result.table_type or "").lower()
    issues = []
    if table_type == "dimension" and layer != "DIM":
        issues.append(f"{layer}/dimension: dimension必须与DIM配对")
    if layer == "DIM" and table_type != "dimension":
        issues.append(f"DIM/{table_type}: DIM必须与dimension配对")
    if layer == "DWS" and table_type != "fact":
        issues.append(f"DWS/{table_type}: DWS必须与fact配对")
    if table_type == "bridge" and layer != "DWD":
        issues.append(f"{layer}/bridge: bridge必须与DWD配对")
    if layer == "OTHER" and table_type == "fact":
        issues.append(
            "OTHER/fact: OTHER不能作为ODS代理；"
            "中间层业务事实必须在DWD/DWS中选择"
        )
    if not issues:
        return {}
    return {"inconsistent_layer_table_types": issues}


def _select_aggregation_evidence(
    query: Any,
    metric_output_names: set[str],
    technical_output_names: set[str],
) -> tuple[bool, set[str]]:
    """Return confirmed metric aggregation and ambiguous MIN/MAX evidence."""
    try:
        from sqlglot import exp
    except Exception:
        return False, set()

    ambiguous_min_max = set()
    for projection in query.expressions:
        for function in projection.find_all(exp.Func):
            if function.find_ancestor(exp.Window) is not None:
                continue
            function_name = str(function.sql_name() or "").upper()
            if function_name in {"MIN", "MAX"}:
                source_columns = list(function.find_all(exp.Column))
                source_name = (
                    _canonical_column_name(source_columns[0].name)
                    if len(source_columns) == 1
                    else ""
                )
                output_name = _canonical_column_name(projection.alias_or_name)
                if (
                    query.args.get("group") is None
                    or not source_name
                    or output_name in metric_output_names
                ):
                    return True, ambiguous_min_max
                if output_name in technical_output_names:
                    ambiguous_min_max.add(
                        f"{function_name}({source_name}) AS {output_name}"
                    )
                    continue
                return True, ambiguous_min_max
            if function_name in KNOWN_METRIC_AGGREGATE_FUNCTIONS:
                return True, ambiguous_min_max
            if (
                isinstance(function, exp.AggFunc)
                and function_name not in NON_METRIC_AGGREGATE_FUNCTIONS
            ):
                return True, ambiguous_min_max
    return False, ambiguous_min_max


def _source_output_names(query: Any, output_names: set[str]) -> set[str]:
    """Map selected output aliases to their source-column names."""
    try:
        from sqlglot import exp
    except Exception:
        return set()

    source_names = set()
    for projection in query.expressions:
        if getattr(projection, "is_star", False):
            source_names.update(output_names)
            continue
        output_name = _canonical_column_name(projection.alias_or_name)
        if output_name not in output_names:
            continue
        expression = (
            projection.this
            if isinstance(projection, exp.Alias)
            else projection
        )
        source_columns = list(expression.find_all(exp.Column))
        if isinstance(expression, exp.Column):
            source_columns.insert(0, expression)
        canonical_sources = {
            _canonical_column_name(column.name) for column in source_columns
        }
        if len(canonical_sources) == 1:
            source_names.update(canonical_sources)
    return source_names


def _query_aggregation_evidence(
    query: Any,
    metric_output_names: set[str],
    technical_output_names: set[str],
    inherited_ctes: dict[str, Any] | None = None,
    seen_ctes: set[str] | None = None,
) -> tuple[bool, set[str]]:
    """Return metric and ambiguous aggregation evidence for the driver.

    Aggregation inside a joined lookup subquery can enrich a retained driving
    row without changing the target grain. Pure GROUP BY deduplication and
    technical MIN/MAX selection remain valid DWD operations, while metric
    aggregates in the target SELECT or its driving CTE/subquery indicate DWS.
    """
    try:
        from sqlglot import exp
    except Exception:
        return False, set()

    while isinstance(query, (exp.Subquery, exp.Paren)):
        query = query.this
    if not isinstance(query, exp.Select):
        return False, set()

    ctes = dict(inherited_ctes or {})
    for cte in query.ctes:
        name = str(cte.alias_or_name or "").strip().casefold()
        if name:
            ctes[name] = cte.this

    has_metric_aggregation, ambiguous_min_max = _select_aggregation_evidence(
        query,
        metric_output_names,
        technical_output_names,
    )
    if has_metric_aggregation:
        return True, ambiguous_min_max
    source_technical_output_names = _source_output_names(
        query,
        technical_output_names,
    )

    from_clause = query.args.get("from") or query.args.get("from_")
    source = getattr(from_clause, "this", None)
    if isinstance(source, exp.Subquery):
        nested_metric, nested_ambiguous = _query_aggregation_evidence(
            source,
            metric_output_names,
            source_technical_output_names,
            ctes,
            seen_ctes,
        )
        return nested_metric, ambiguous_min_max | nested_ambiguous
    if not isinstance(source, exp.Table):
        return False, ambiguous_min_max

    source_name = str(source.name or "").strip().casefold()
    if not source_name or source_name not in ctes:
        return False, ambiguous_min_max
    seen = set(seen_ctes or ())
    if source_name in seen:
        return False, ambiguous_min_max
    seen.add(source_name)
    nested_metric, nested_ambiguous = _query_aggregation_evidence(
        ctes[source_name],
        metric_output_names,
        source_technical_output_names,
        ctes,
        seen,
    )
    return nested_metric, ambiguous_min_max | nested_ambiguous


def _target_query_aggregation_evidence(
    etl_sql: str,
    metric_output_names: set[str],
    technical_output_names: set[str],
) -> tuple[bool, set[str]] | None:
    """Inspect INSERT/SELECT driving queries for aggregation evidence."""
    if not str(etl_sql or "").strip():
        return None
    try:
        import sqlglot
        from sqlglot import exp
        from sqlglot.errors import ErrorLevel

        statements = sqlglot.parse(
            etl_sql,
            dialect="doris",
            error_level=ErrorLevel.IGNORE,
        )
    except Exception:
        return None

    queries = []
    for statement in statements:
        if isinstance(statement, exp.Insert):
            query = statement.args.get("expression") or statement.args.get(
                "source"
            )
            if query is not None:
                queries.append(query)
        elif isinstance(statement, exp.Select):
            queries.append(statement)
    if not queries:
        return None
    has_metric_aggregation = False
    ambiguous_min_max = set()
    for query in queries:
        query_metric, query_ambiguous = _query_aggregation_evidence(
            query,
            metric_output_names,
            technical_output_names,
        )
        has_metric_aggregation = has_metric_aggregation or query_metric
        ambiguous_min_max.update(query_ambiguous)
    return has_metric_aggregation, ambiguous_min_max


def validate_layer_sql_consistency(
    result: TableInspectResult,
    ctx: TableContext,
) -> dict[str, list[str]]:
    """Validate that DWD does not reduce the target driving-row grain."""
    if str(result.inferred_layer or "").upper() != "DWD":
        return {}
    metric_output_names = {
        _canonical_column_name(name)
        for group_name in (
            "atomic_metrics",
            "derived_metrics",
            "calculated_metrics",
        )
        for name in _metric_names_from_items(result.columns.get(group_name))
    }
    technical_output_names = _technical_output_names(result)
    evidence = _target_query_aggregation_evidence(
        ctx.etl_sql,
        metric_output_names,
        technical_output_names,
    )
    if evidence is None:
        return {}
    has_metric_aggregation, ambiguous_min_max = evidence
    validation = {}
    if has_metric_aggregation:
        validation["inconsistent_layer_sql"] = [
            "DWD候选的目标行驱动查询包含指标聚合；请重新判断DWS或其他合法层级"
        ]
    elif ambiguous_min_max:
        validation[AMBIGUOUS_MIN_MAX_WARNING_KEY] = [
            f"{expression}: 无法仅凭同名MIN/MAX确定技术选值或业务汇总"
            for expression in sorted(ambiguous_min_max)
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


def _canonical_table_identity(table_name: Any) -> str:
    text = str(table_name or "").strip().replace("`", "").replace('"', "")
    return ".".join(
        part.strip().casefold() for part in text.split(".") if part.strip()
    )


def _canonical_short_table_name(table_name: Any) -> str:
    return _canonical_table_identity(table_name).split(".")[-1]


def _matching_table_identities(
    table_name: Any,
    identities,
) -> list[str]:
    canonical_identities = {
        _canonical_table_identity(identity)
        for identity in identities
        if _canonical_table_identity(identity)
    }
    wanted = _canonical_table_identity(table_name)
    if not wanted:
        return []
    if "." in wanted:
        if wanted in canonical_identities:
            return [wanted]
        short_matches = sorted(
            identity
            for identity in canonical_identities
            if _canonical_short_table_name(identity)
            == _canonical_short_table_name(wanted)
        )
        if len(short_matches) == 1 and "." not in short_matches[0]:
            return short_matches
        return []
    short_name = _canonical_short_table_name(wanted)
    return sorted(
        identity
        for identity in canonical_identities
        if _canonical_short_table_name(identity) == short_name
    )


def _technical_output_names(result: TableInspectResult) -> set[str]:
    return {
        _canonical_column_name(item.get("name"))
        for item in result.columns.get("others", [])
        if str(item.get("role") or "").strip().casefold() == "technical"
    }


def _canonical_column_name(column_name: Any) -> str:
    return (
        str(column_name or "")
        .strip()
        .replace("`", "")
        .replace('"', "")
        .casefold()
    )


def _atomic_metric_tables_for_validation(
    result: TableInspectResult, ctx: TableContext
) -> dict[str, set[str]]:
    tables: dict[str, set[str]] = {}
    same_table_metrics = {
        _canonical_column_name(name)
        for name in _metric_names_from_items(result.atomic_metrics)
    }
    if same_table_metrics:
        tables[_canonical_table_identity(result.table_name)] = (
            same_table_metrics
        )
    for table_name, groups in (ctx.upstream_metric_groups or {}).items():
        if not isinstance(groups, dict):
            continue
        names = {
            _canonical_column_name(name)
            for name in _metric_names_from_items(groups.get("atomic_metrics"))
        }
        if names:
            identity = _canonical_table_identity(table_name)
            tables.setdefault(identity, set()).update(names)
    return tables


def _base_metric_candidate_tables(
    base_metric: str, atomic_metric_tables: dict[str, set[str]]
) -> list[str]:
    metric_key = _canonical_column_name(base_metric)
    return sorted(
        table_name
        for table_name, metric_names in atomic_metric_tables.items()
        if metric_key in metric_names
    )


def _split_column_identifier(identifier: Any) -> tuple[str, str]:
    text = str(identifier or "").strip().replace("`", "")
    if "." not in text:
        return "", _canonical_column_name(text)
    table_name, column_name = text.rsplit(".", 1)
    return (
        _canonical_table_identity(table_name),
        _canonical_column_name(column_name),
    )


def validate_upstream_metric_layer_consistency(
    result: TableInspectResult,
    ctx: TableContext,
) -> dict[str, list[str]]:
    """Prevent DWD from publishing a joined public-metric grain."""
    if (
        str(result.inferred_layer or "").upper() != "DWD"
        or not result.is_fact_table
        or not ctx.upstream_metric_groups
    ):
        return {}

    target_metrics = {
        _canonical_column_name(name)
        for group in (
            "atomic_metrics",
            "derived_metrics",
            "calculated_metrics",
        )
        for name in _metric_names_from_items(result.columns.get(group))
    }
    if not target_metrics:
        return {}

    upstream_identities = {
        _canonical_table_identity(table_name)
        for table_name in ctx.upstream_tables
        if _canonical_table_identity(table_name)
    }
    aggregation_evidence = _target_query_aggregation_evidence(
        ctx.etl_sql,
        target_metrics,
        _technical_output_names(result),
    )
    if (
        len(upstream_identities) == 1
        and aggregation_evidence is not None
        and not aggregation_evidence[0]
    ):
        # A row-preserving pass-through from one detail source remains DWD;
        # metric classification alone does not create a public DWS grain.
        return {}

    upstream_metrics: dict[str, set[str]] = {}
    for table_name, groups in (ctx.upstream_metric_groups or {}).items():
        if not isinstance(groups, dict):
            continue
        metric_names = {
            _canonical_column_name(name)
            for group in (
                "atomic_metrics",
                "derived_metrics",
                "calculated_metrics",
            )
            for name in _metric_names_from_items(groups.get(group))
        }
        if metric_names:
            upstream_metrics[_canonical_table_identity(table_name)] = (
                metric_names
            )
    if not upstream_metrics:
        return {}

    publications = set()
    for edge in ctx.column_lineage or []:
        if not isinstance(edge, dict):
            continue
        source_table, source_column = _split_column_identifier(
            edge.get("source")
        )
        _target_table, target_column = _split_column_identifier(
            edge.get("target")
        )
        if target_column not in target_metrics:
            continue
        matching_tables = _matching_table_identities(
            source_table,
            upstream_metrics,
        )
        if len(matching_tables) != 1:
            continue
        upstream_table = matching_tables[0]
        if source_column in upstream_metrics[upstream_table]:
            publications.add(
                f"{target_column}<-{upstream_table}.{source_column}"
            )

    if not publications:
        return {}
    return {
        "inconsistent_upstream_metric_layers": sorted(publications),
    }


def _lineage_base_metric_tables(
    ctx: TableContext,
    *,
    target_metric: str,
    base_metric: str,
) -> list[str]:
    target_key = _canonical_column_name(target_metric)
    base_key = _canonical_column_name(base_metric)
    tables = set()
    for edge in ctx.column_lineage or []:
        if not isinstance(edge, dict):
            continue
        _target_table, target_column = _split_column_identifier(
            edge.get("target")
        )
        source_table, source_column = _split_column_identifier(
            edge.get("source")
        )
        if (
            target_column == target_key
            and source_column == base_key
            and source_table
        ):
            tables.add(source_table)
    return sorted(tables)


def _known_upstream_metric_group_tables(ctx: TableContext) -> set[str]:
    return {
        _canonical_table_identity(table_name)
        for table_name in (ctx.upstream_metric_groups or {})
    }


def _actual_upstream_tables(ctx: TableContext) -> set[str]:
    return {
        _canonical_table_identity(table_name)
        for table_name in (ctx.upstream_tables or [])
    }


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
        if not candidates:
            known_group_tables = _known_upstream_metric_group_tables(ctx)
            candidates = [
                table_name
                for table_name in _lineage_base_metric_tables(
                    ctx,
                    target_metric=str(metric.get("name") or ""),
                    base_metric=base_metric,
                )
                if table_name not in known_group_tables
            ]
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
    actual_upstream_tables = _actual_upstream_tables(ctx)
    known_group_tables = _known_upstream_metric_group_tables(ctx)
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
            metric_key = _canonical_column_name(base_metric)
            lineage_tables = _lineage_base_metric_tables(
                ctx,
                target_metric=metric_name,
                base_metric=base_metric,
            )
            known_table_identities = (
                set(atomic_metric_tables)
                | actual_upstream_tables
                | known_group_tables
                | set(lineage_tables)
            )
            matching_tables = _matching_table_identities(
                base_metric_table,
                known_table_identities,
            )
            if len(matching_tables) != 1:
                issues["invalid_base_metric_tables"].append(
                    f"{metric_name}:{base_metric_table}"
                )
                continue
            table_key = matching_tables[0]
            table_metrics = atomic_metric_tables.get(table_key)
            if table_metrics is None:
                if (
                    table_key not in actual_upstream_tables
                    or table_key not in lineage_tables
                ):
                    issues["invalid_base_metric_tables"].append(
                        f"{metric_name}:{base_metric_table}"
                    )
                elif table_key in known_group_tables:
                    issues["invalid_base_metrics"].append(
                        f"{metric_name}:{base_metric_table}.{base_metric}"
                    )
                continue
            if metric_key not in table_metrics:
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


def validate_inspection_result(
    result: TableInspectResult,
    ctx: TableContext,
    *,
    validate_publication_contract: bool = False,
) -> TableInspectResult:
    """Rebuild deterministic validation after a result is transformed."""
    orchestration_validation = {
        key: list(values)
        for key, values in (result.validation or {}).items()
        if key in ORCHESTRATION_VALIDATION_KEYS and values
    }
    ddl_columns = _extract_ddl_column_names(ctx.ddl)
    enrich_metric_relationships(result, ctx)
    result.validation = _merge_validation(
        validate_columns(result, ddl_columns),
        validate_time_periods(result),
        validate_metric_expressions(result),
        validate_primary_entities(result),
        validate_layer_table_type_consistency(result),
        validate_layer_sql_consistency(result, ctx),
        validate_upstream_metric_layer_consistency(result, ctx),
        validate_metric_relationships(result, ctx),
        (
            validate_generate_inspection_contract(
                result,
                ddl_columns,
            )
            if validate_publication_contract
            else {}
        ),
        orchestration_validation,
    )
    synchronize_result_issues(result)
    return result


class TableInspector:
    def __init__(
        self,
        api_key: str,
        *,
        model: str = "deepseek-v4-flash",
        base_url: str | None = None,
        cache_file: Path = None,
        max_retries: int = 1,
        parallelism: int = 2,
        request_timeout: int = 60,
        min_cacheable_confidence: float = DEFAULT_MIN_CACHEABLE_CONFIDENCE,
        resume_cache: dict[str, Any] | None = None,
        validate_publication_contract: bool = False,
        catalog_snapshot_hash: str = "",
        asset_manifest_hash: str = "",
    ):
        self.api_key = api_key
        self.model = model
        self.base_url = normalize_chat_completions_url(base_url)
        self.cache_file = cache_file
        self.max_retries = max(0, int(max_retries))
        self.parallelism = max(1, int(parallelism))
        self.request_timeout = max(1, int(request_timeout))
        self.min_cacheable_confidence = float(min_cacheable_confidence)
        self.cache = {}
        self.resume_cache = dict(resume_cache or {})
        self.catalog_snapshot_hash = str(catalog_snapshot_hash or "")
        self.asset_manifest_hash = str(asset_manifest_hash or "")
        self.validate_publication_contract = bool(
            validate_publication_contract
        )
        self._cache_lock = threading.RLock()
        self.progress_callback: Callable[[dict[str, Any]], None] | None = None
        self.result_callback: Callable[[TableInspectResult], None] | None = (
            None
        )
        self._load_cache()
        if self._purge_invalidated_cache_variants():
            self._save_cache()

    def _load_cache(self):
        with self._cache_lock:
            if self.cache_file and self.cache_file.exists():
                try:
                    payload = json.loads(
                        self.cache_file.read_text(encoding=TEXT_ENCODING)
                    )
                    self.cache = payload if isinstance(payload, dict) else {}
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

    def _purge_invalidated_cache_variants(self) -> bool:
        """Persistently remove cache entries rejected by generate."""
        changed = False
        with self._cache_lock:
            for table_name, resume_entry in self.resume_cache.items():
                if not isinstance(resume_entry, dict):
                    continue
                invalid_hashes = {
                    str(value)
                    for value in (
                        resume_entry.get("invalid_context_hashes") or []
                    )
                    if value
                }
                cached_data = self.cache.get(table_name)
                if not invalid_hashes or not isinstance(cached_data, dict):
                    continue
                raw_variants = cached_data.get("variants")
                variants = (
                    dict(raw_variants)
                    if isinstance(raw_variants, dict)
                    else {}
                )
                retained_variants = {
                    cache_hash: variant
                    for cache_hash, variant in variants.items()
                    if cache_hash not in invalid_hashes
                }
                current_hash = str(cached_data.get("hash") or "")
                if current_hash in invalid_hashes:
                    if not retained_variants:
                        self.cache.pop(table_name, None)
                    else:
                        replacement_hash, replacement = list(
                            retained_variants.items()
                        )[-1]
                        replacement_result = (
                            replacement.get("result")
                            if isinstance(replacement, dict)
                            else None
                        )
                        if not isinstance(replacement_result, dict):
                            self.cache.pop(table_name, None)
                        else:
                            self.cache[table_name] = {
                                "hash": replacement_hash,
                                "result": replacement_result,
                                "content_sha256": str(
                                    replacement.get("content_sha256") or ""
                                ),
                                "variants": retained_variants,
                            }
                    changed = True
                    continue
                if retained_variants != variants:
                    cached_data["variants"] = retained_variants
                    changed = True
        return changed

    @staticmethod
    def _cached_result_for_hash(
        cached_data: Any,
        current_hash: str,
    ) -> dict[str, Any] | None:
        if not isinstance(cached_data, dict):
            return None
        if cached_data.get("hash") == current_hash:
            result = cached_data.get("result")
            digest = cached_data.get("content_sha256")
        else:
            variants = cached_data.get("variants")
            if not isinstance(variants, dict):
                return None
            variant = variants.get(current_hash)
            if not isinstance(variant, dict):
                return None
            result = variant.get("result")
            digest = variant.get("content_sha256")
        if not isinstance(result, dict) or not isinstance(digest, str):
            return None
        try:
            actual_digest = cache_result_digest(result)
        except (TypeError, ValueError):
            return None
        if digest != actual_digest:
            return None
        return result

    def _store_cached_result(
        self,
        table_name: str,
        current_hash: str,
        result: TableInspectResult,
    ) -> None:
        result_data = result_to_cache_dict(result)
        result_digest = cache_result_digest(result_data)
        cached_data = self.cache.get(table_name)
        variants: dict[str, dict[str, Any]] = {}
        if isinstance(cached_data, dict):
            raw_variants = cached_data.get("variants")
            if isinstance(raw_variants, dict):
                variants.update(
                    {
                        str(cache_hash): variant
                        for cache_hash, variant in raw_variants.items()
                        if isinstance(variant, dict)
                    }
                )
            previous_hash = str(cached_data.get("hash") or "")
            previous_result = cached_data.get("result")
            previous_digest = cached_data.get("content_sha256")
            try:
                previous_digest_matches = (
                    isinstance(previous_result, dict)
                    and isinstance(previous_digest, str)
                    and previous_digest == cache_result_digest(previous_result)
                )
            except (TypeError, ValueError):
                previous_digest_matches = False
            if previous_hash and previous_digest_matches:
                variants.setdefault(
                    previous_hash,
                    {
                        "result": previous_result,
                        "content_sha256": previous_digest,
                    },
                )

        variants.pop(current_hash, None)
        variants[current_hash] = {
            "result": result_data,
            "content_sha256": result_digest,
        }
        while len(variants) > MAX_CACHE_VARIANTS_PER_TABLE:
            variants.pop(next(iter(variants)))
        self.cache[table_name] = {
            "hash": current_hash,
            "result": result_data,
            "content_sha256": result_digest,
            "variants": variants,
        }

    def _compute_hash(self, ctx: TableContext) -> str:
        # 缓存 hash 需要包含所有影响 LLM 判断的特征与 prompt schema 版本。
        prompt_layer = _prompt_layer(ctx)
        upstream_layers = _prompt_table_layers(
            ctx,
            ctx.upstream_table_layers,
        )
        downstream_layers = _prompt_table_layers(
            ctx,
            ctx.downstream_table_layers,
        )
        content = (
            f"{PROMPT_VERSION}|publication_contract="
            f"{self.validate_publication_contract}|"
            f"catalog_snapshot={self.catalog_snapshot_hash}|"
            f"asset_manifest={self.asset_manifest_hash}|"
            f"{self.model}|{self.base_url}|temperature=0|"
            f"{ctx.table_name}|{prompt_layer}|{ctx.ddl}|"
            f"{ctx.etl_sql}|{ctx.upstream_tables}|{ctx.downstream_tables}|"
            f"{upstream_layers}|{downstream_layers}|"
            f"{ctx.depth_from_ods}|{ctx.upstream_metric_groups}|"
            f"{ctx.downstream_entity_publication_features}|"
            f"{ctx.column_lineage}|{ctx.declared_data_domain}|"
            f"{ctx.declared_business_area}|{ctx.business_domain_options}|"
            f"{ctx.business_semantics_options}|{ctx.project_context}"
        )
        return hashlib.sha256(content.encode(TEXT_ENCODING)).hexdigest()

    def persist_finalized_results(
        self,
        pairs: list[tuple[TableContext, TableInspectResult]],
    ) -> None:
        """Persist post-propagation results rather than only raw API output."""
        cache_changed = False
        for ctx, result in pairs:
            current_hash = self._compute_hash(ctx)
            result.context_hash = current_hash
            result.catalog_snapshot_hash = self.catalog_snapshot_hash
            result.asset_manifest_hash = self.asset_manifest_hash
            if (
                result.resume_eligible
                and result.status != "blocked"
                and result.confidence >= self.min_cacheable_confidence
            ):
                with self._cache_lock:
                    self._store_cached_result(
                        ctx.table_name,
                        current_hash,
                        result,
                    )
                cache_changed = True
            if self.result_callback:
                self.result_callback(result)
        if cache_changed:
            self._save_cache()

    def _restored_result(
        self,
        cache: dict[str, Any],
        ctx: TableContext,
        current_hash: str,
        *,
        source: str,
    ) -> TableInspectResult | None:
        cached_result = self._cached_result_for_hash(
            cache.get(ctx.table_name),
            current_hash,
        )
        if cached_result is None:
            return None
        try:
            cache_policy = InspectionCachePolicy.from_dict(
                cached_result.get("cache_policy")
            )
            if not cache_policy.matches_inputs(
                context_hash=current_hash,
                catalog_snapshot_hash=self.catalog_snapshot_hash,
                asset_manifest_hash=self.asset_manifest_hash,
            ):
                return None
            cached_view = dict_to_result(
                cached_result,
                table_name=ctx.table_name,
                declared_layer=ctx.layer,
            )
            if (
                cached_view.table_name != ctx.table_name
                or cached_view.context_hash != current_hash
                or cached_view.catalog_snapshot_hash
                != self.catalog_snapshot_hash
                or cached_view.asset_manifest_hash != self.asset_manifest_hash
                or cached_view.parsed_candidate is None
                or cached_view.parsed_candidate.table_name != ctx.table_name
            ):
                return None
            if cached_view.raw_response is not None and (
                cached_view.raw_response.table_name != ctx.table_name
                or cached_view.parsed_candidate.raw_response_hash
                != cached_view.raw_response.content_hash
            ):
                return None
            replayed_response = {
                "choices": [
                    {
                        "message": {
                            "content": json.dumps(
                                cached_view.parsed_candidate.payload,
                                ensure_ascii=False,
                                separators=(",", ":"),
                            )
                        }
                    }
                ]
            }
            restored_result = parse_response(
                ctx.table_name,
                replayed_response,
                ctx.layer,
                raw_response=cached_view.raw_response,
            )
            restored_result.raw_response = cached_view.raw_response
            restored_result.parsed_candidate = cached_view.parsed_candidate
            restored_result.retry_count = cached_view.retry_count
            restored_result.first_attempt_inferred_layer = (
                cached_view.first_attempt_inferred_layer
            )
            validate_inspection_result(
                restored_result,
                ctx,
                validate_publication_contract=(
                    self.validate_publication_contract
                ),
            )
        except (
            InvalidInspectionCacheError,
            UnknownInspectionIssueError,
            TypeError,
            ValueError,
        ):
            return None
        if (
            restored_result.status == "blocked"
            or restored_result.confidence < self.min_cacheable_confidence
        ):
            return None
        restored_result.context_hash = current_hash
        restored_result.catalog_snapshot_hash = self.catalog_snapshot_hash
        restored_result.asset_manifest_hash = self.asset_manifest_hash
        restored_result.reuse_source = source
        restored_result.resume_eligible = True
        return restored_result

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
        }
        data = {
            "model": self.model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.0,
        }

        try:
            endpoint = urlparse(self.base_url)
            endpoint_host = endpoint.hostname
        except ValueError as error:
            raise InspectionConfigurationError(
                "DeepSeek endpoint configuration is invalid"
            ) from error
        if endpoint.scheme not in {"http", "https"} or not endpoint_host:
            raise InspectionConfigurationError(
                "DeepSeek endpoint configuration is invalid"
            )
        try:
            req = urllib.request.Request(
                self.base_url,
                data=json.dumps(data).encode(TEXT_ENCODING),
                headers=headers,
                method="POST",
            )
            with urllib.request.urlopen(
                req, timeout=self.request_timeout
            ) as response:
                response_body = response.read()
        except HTTPError as error:
            status_code = int(error.code)
            evidence = (
                IssueEvidence(
                    kind="http_status",
                    values=(str(status_code),),
                ),
            )
            if status_code in AUTHENTICATION_HTTP_STATUS_CODES:
                raise InspectionAuthenticationError(
                    "DeepSeek API authentication was rejected",
                    evidence=evidence,
                ) from error
            if (
                400 <= status_code < 500
                and status_code not in RETRYABLE_HTTP_STATUS_CODES
            ):
                raise InspectionRequestRejectedError(
                    "DeepSeek API request configuration was rejected",
                    evidence=evidence,
                ) from error
            raise InspectionTransportError(
                "DeepSeek API transport failed",
                evidence=evidence,
            ) from error
        except ValueError as error:
            raise InspectionConfigurationError(
                "DeepSeek endpoint configuration is invalid"
            ) from error
        except (HTTPException, OSError, TimeoutError) as error:
            raise InspectionTransportError(
                "DeepSeek API transport failed"
            ) from error
        try:
            return response_body.decode(TEXT_ENCODING)
        except UnicodeError as error:
            raise InspectionContentParseError(
                f"DeepSeek API 响应不是有效 {TEXT_ENCODING}: {error}"
            ) from error

    def inspect(
        self,
        ctx: TableContext,
        *,
        progress_context: dict[str, Any] | None = None,
    ) -> TableInspectResult:
        current_hash = self._compute_hash(ctx)

        restored_result = self._restored_result(
            self.resume_cache,
            ctx,
            current_hash,
            source="checkpoint",
        )
        if restored_result is not None:
            self._emit_progress(
                "checkpoint_hit", ctx, progress_context=progress_context
            )
            return restored_result

        resume_entry = self.resume_cache.get(ctx.table_name) or {}
        invalid_context_hashes = resume_entry.get("invalid_context_hashes")
        should_bypass_cache = bool(
            isinstance(invalid_context_hashes, list)
            and current_hash in invalid_context_hashes
        )
        if should_bypass_cache:
            self._emit_progress(
                "checkpoint_retry", ctx, progress_context=progress_context
            )
            restored_result = None
        else:
            with self._cache_lock:
                restored_result = self._restored_result(
                    self.cache,
                    ctx,
                    current_hash,
                    source="cache",
                )
        if restored_result is not None:
            # A transient API/parse failure or validation-blocked result must
            # not poison future runs. Retry budget is intentionally excluded
            # from the semantic context hash so increasing retries only reruns
            # failed tables.
            self._emit_progress(
                "cache_hit", ctx, progress_context=progress_context
            )
            return restored_result

        prompt = build_prompt(ctx)
        result = None
        last_usable_result = None
        used_retry_fallback = False
        first_attempt_inferred_layer = ""
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
            except InspectionBoundaryError as error:
                result = TableInspectResult(
                    table_name=ctx.table_name,
                    declared_layer=ctx.layer,
                    inferred_layer="OTHER",
                    table_type="other",
                    confidence=0.0,
                    reasoning_steps=[f"分类异常: {str(error)}"],
                    issues=(error.to_issue(ctx.table_name),),
                    retry_count=attempt,
                )
                if attempt == 0:
                    first_attempt_inferred_layer = result.inferred_layer
                result.first_attempt_inferred_layer = (
                    first_attempt_inferred_layer
                )
                self._emit_progress(
                    "api_error",
                    ctx,
                    progress_context=progress_context,
                    attempt=attempt + 1,
                    max_attempts=self.max_retries + 1,
                    error=str(error),
                )
                if not error.retryable or attempt >= self.max_retries:
                    if last_usable_result is not None:
                        failure_issues = result.issues
                        result = last_usable_result
                        used_retry_fallback = True
                        result.retry_count = attempt
                        result.reasoning_steps.append(
                            f"重试异常，保留上次可用结果: {str(error)}"
                        )
                        result.issues = sort_issues(
                            tuple(result.issues) + tuple(failure_issues)
                        )
                    break
                continue
            except Exception as error:
                internal_error = InspectionInternalError(
                    f"inspection request boundary failed: {error}",
                    table_name=ctx.table_name,
                    stage="parse",
                    cause=error,
                )
                raise internal_error from error

            raw_response = RawInspectionResponse.create(
                table_name=ctx.table_name,
                model=self.model,
                endpoint=self.base_url,
                context_hash=current_hash,
                body=resp_str,
            )
            try:
                resp_json = json.loads(resp_str)
                if not isinstance(resp_json, dict):
                    raise InspectionContentParseError(
                        "API response envelope must be a JSON object"
                    )
                result = parse_response(
                    ctx.table_name,
                    resp_json,
                    ctx.layer,
                    raw_response=raw_response,
                )
            except json.JSONDecodeError as error:
                parse_error = InspectionContentParseError(str(error))
                parse_error.__cause__ = error
                result = _parse_failure_result(
                    table_name=ctx.table_name,
                    declared_layer=ctx.layer,
                    raw_response=raw_response,
                    error=parse_error,
                )
            except InspectionContentParseError as error:
                result = _parse_failure_result(
                    table_name=ctx.table_name,
                    declared_layer=ctx.layer,
                    raw_response=raw_response,
                    error=error,
                )
            except Exception as error:
                internal_error = InspectionInternalError(
                    f"inspection parser failed: {error}",
                    table_name=ctx.table_name,
                    stage="parse",
                    cause=error,
                )
                raise internal_error from error
            result.retry_count = attempt
            if attempt == 0:
                first_attempt_inferred_layer = result.inferred_layer
            result.first_attempt_inferred_layer = first_attempt_inferred_layer
            try:
                validate_inspection_result(
                    result,
                    ctx,
                    validate_publication_contract=(
                        self.validate_publication_contract
                    ),
                )
            except Exception as error:
                internal_error = InspectionInternalError(
                    f"inspection validation failed: {error}",
                    table_name=ctx.table_name,
                    stage="local_validation",
                    cause=error,
                )
                raise internal_error from error
            if result.confidence > 0:
                last_usable_result = result
            elif (
                last_usable_result is not None and attempt >= self.max_retries
            ):
                failure = next(
                    iter(result.reasoning_steps),
                    "返回结果不可用",
                )
                failure_issues = result.issues
                result = last_usable_result
                used_retry_fallback = True
                result.retry_count = attempt
                result.reasoning_steps.append(
                    f"重试异常，保留上次可用结果: {failure}"
                )
                result.issues = sort_issues(
                    tuple(result.issues) + tuple(failure_issues)
                )
                break
            if (
                result.status == "passed"
                or result.validation.get(DDL_COLUMNS_UNAVAILABLE_ERROR_KEY)
                or attempt >= self.max_retries
            ):
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
            prompt = build_retry_prompt(
                ctx,
                result,
                _extract_ddl_column_names(ctx.ddl),
            )

        result.context_hash = current_hash
        result.catalog_snapshot_hash = self.catalog_snapshot_hash
        result.asset_manifest_hash = self.asset_manifest_hash
        result.reuse_source = ""
        result.resume_eligible = not used_retry_fallback
        if (
            not used_retry_fallback
            and result.status != "blocked"
            and result.confidence >= self.min_cacheable_confidence
        ):
            with self._cache_lock:
                self._store_cached_result(ctx.table_name, current_hash, result)
                self._save_cache()

        return result

    def inspect_batch(
        self, contexts: list[TableContext]
    ) -> list[TableInspectResult]:
        total = len(contexts)
        batch_failed = threading.Event()

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
            except InspectionInternalError as error:
                self._emit_progress(
                    "unexpected_error",
                    ctx,
                    progress_context=progress_context,
                    error=str(error),
                )
                batch_failed.set()
                raise
            except Exception as error:
                self._emit_progress(
                    "unexpected_error",
                    ctx,
                    progress_context=progress_context,
                    error=str(error),
                )
                batch_failed.set()
                internal_error = InspectionInternalError(
                    f"inspection worker failed: {error}",
                    table_name=ctx.table_name,
                    stage="local_validation",
                    cause=error,
                    context="worker",
                )
                raise internal_error from error
            if self.result_callback and not batch_failed.is_set():
                try:
                    self.result_callback(result)
                except BaseException:
                    batch_failed.set()
                    raise
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
        indexed_contexts = iter(enumerate(contexts, start=1))
        results_by_index: dict[int, TableInspectResult] = {}
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            pending = {}

            def submit_next() -> bool:
                if batch_failed.is_set():
                    return False
                try:
                    item = next(indexed_contexts)
                except StopIteration:
                    return False
                pending[executor.submit(inspect_safely, item)] = item[0]
                return True

            for _ in range(max_workers):
                submit_next()

            try:
                while pending:
                    done, _ = wait(
                        tuple(pending),
                        return_when=FIRST_COMPLETED,
                    )
                    completed = [
                        (pending.pop(future), future) for future in done
                    ]
                    for index, future in completed:
                        results_by_index[index] = future.result()
                    for _ in completed:
                        submit_next()
            except BaseException:
                batch_failed.set()
                for future in pending:
                    future.cancel()
                raise

        return [results_by_index[index] for index in range(1, total + 1)]
