# retail_banking 语义冷启动 Benchmark 人工复核汇总

## 最终裁决

`retail_banking` 当前适合作为 **benchmark candidate、weak-label 集和大规模血缘/重构压测基线**，
但不应直接冻结为模型语义冷启动 `gold_v1`。

三组独立人工复核的合并结果：

| 范围 | Accept | Revise | Reject | 合计 |
|---|---:|---:|---:|---:|
| DIM | 19 | 14 | 1 | 34 |
| DWD | 18 | 38 | 6 | 62 |
| DWS | 10 | 8 | 0 | 18 |
| ADS | 3 | 10 | 0 | 13 |
| **下游语义资产** | **50** | **70** | **7** | **127** |

`Accept` 表示核心对象成立，仍需应用全局 gold 规范；`Revise` 需修正后才能评分；
`Reject` 应从正样本撤销，但可保留为 hard negative。

## 已确认通过的基线

- 277 张 analytical ODS 与 schema snapshot/mapping 一一对应，无遗漏、无重复。
- 固定 commit 下的范围口径 `287 = 277 + 6 Spring Batch + 4 tenant-store` 一致。
- 404 张物理表、127 个任务可完整生成和抽取血缘，DAG 无环。
- DWS 业务日期、GROUP BY 和 reversal 的主干逻辑比机械生成版本明显改善。
- 拨备 run/entry 已拆分，明细金额与批次状态可追溯。

## 阻止 gold_v1 的确定性问题

### 1. 源表标签尚未闭合

- 173 张表仍为 `candidate`，不存在唯一人工真值。
- 16 张 `security_excluded` 中有 8 张仍是 `candidate`，状态自相矛盾。
- 至少 17 张当前 `internal` 表有确定性 secret/PII 漏标。
- 12 张 restricted 源表直接进入 DIM/DWD，但没有列级 sensitivity 与
  `drop/hash/tokenize/mask/pass_through` 动作。
- 100 张 `component_source` 当前没有任何真实下游引用，需要
  `recommended_join_target` 或人工确认 ODS-only。

### 2. DIM/DWD 语义深度不足

- 96 个 model 全部只有一个机械生成的主实体，没有声明任何 FK 角色实体。
- 96 个 model 均缺业务日期/event/effective/snapshot 时间语义。
- 95/96 个 task 没有真正投影多源语义字段；大多数仍是直拷或无效 LEFT JOIN。
- 25 张 DWD 使用不存在于 canonical catalog 的 business-process code。
- `m_loan` / `m_savings_account` / `m_share_account` / `m_wc_loan`
  四类账户源将时变余额和累计金额整体复制进 DIM，应拆稳定维度与日快照。

### 3. 需撤销的 7 个正样本

- `dim_guarantor`
- `dwd_credit_report`
- `dwd_customer_identifier`
- `dwd_loan_interest_recalculation`
- `dwd_loan_rate_period`
- `dwd_wc_loan_lock_event`
- `dwd_wc_payment_allocation_rule`

上述资产应转为受限 satellite/document vault、bridge/rule/snapshot 或 hard negative，不能以
当前的 DIM/DWD fact 标签进入 gold。

### 4. DWS/ADS 金融指标标签不完整

- 18 张 DWS 的 `SUM`/`COUNT` 结果均被标为 `atomic_metrics`，应主要归为 derived metrics。
- 缺少 currency source、unit、sign convention、reversal policy、flow/state、
  additivity/semi-additivity 与允许汇总维度。
- 10 张名含 `monitor` 的 ADS 只有字段透传和简单均值，没有阈值、异常、待处理或比率语义。
- 277 行源映射中有 200 行 business-process code 不在 canonical catalog 内。

### 5. 现有 benchmark runner 不能评估完整语义

- 当前主要评分 DIM/DWD/DWS layer，ODS/ADS 被目录角色直接暴露。
- metrics/entities/grain 主要统计是否存在，没有 exact/F1/公式等价评分。
- 路径、表名前缀、taxonomy `project_context`、`_daily`/`monitor` 等存在强标签泄漏。
- 正式测试必须将 input bundle 与 private gold 置于不同权限边界。

## 建议的 benchmark 资产分层

1. **weak_labels_v0**：保留当前 277 源映射和 127 下游资产，用于开发、压测与发现错误，
   不用于最终准确率。
2. **seed_gold_candidates**：将 50 个 Accept 资产在补齐全局 process/entity/date/metric 规范后，
   作为双人独立标注的起点。
3. **revision_queue**：70 个 Revise 资产，保留修订前/后答案和 adjudication rationale。
4. **hard_negatives**：7 个 Reject 资产加上 security/technical/rule 误分样本，
   评估模型是否能拒绝机械分层。

## 发布 gold_v1 前的最小顺序

1. 收敛安全状态，补 17 张漏标表和所有直接下游的列级 masking gold。
2. 撤销 7 个错误正样本，修正确定性数据域错分和四类账户的维度/快照边界。
3. 闭合 business-process 字典，为每张受评表补主实体、角色实体、复合粒度和业务日期。
4. 重新裁决 DWS 指标分类和金融可加性，对 10 张 monitor ADS 改名或增加真实应用规则。
5. 定义 private gold schema，增加 allowed alternatives、partial credit 和公式规范化评分。
6. 构建 Named/taxonomy-assisted、Prefixless/role-blind、Partially-obfuscated 和 Template-holdout 四档输入。
7. 至少两名 reviewer 独立标注 50 个 seed candidates，不一致项交由 adjudicator 裁决。

## 复核报告

- `work/retail_banking_source_mapping_human_review.md`
- `work/retail_banking_dim_dwd_human_review.md`
- `work/retail_banking_dws_ads_benchmark_human_review.md`
