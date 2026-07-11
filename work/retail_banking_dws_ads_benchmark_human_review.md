# retail_banking DWS / ADS 与语义冷启动 Benchmark 人工复核

复核范围：`warehouses/retail_banking` 的 18 张 DWS、13 张 ADS、277 张源表的完整层级映射，以及现有 `benchmarks/table_inspector_layer` 冷启动流程。复核仅检查资产并记录结论，没有修改仓库资产。

## 结论

| 范围 | Accept | Revise | Reject | 合计 |
|---|---:|---:|---:|---:|
| DWS | 10 | 8 | 0 | 18 |
| ADS | 3 | 10 | 0 | 13 |
| 合计 | 13 | 18 | 0 | 31 |

当前资产适合做 **benchmark 候选集**，但不应直接发布为语义 gold v1。主要 blocker：

1. `fineract_table_mapping.yaml` 中 277 行有 200 行使用了不在 `business_processes.yaml` 中的过程代码，例如 `loan_management`、`dpst_management`、`fina_management`；过程标签无法闭集评分。
2. 现有 benchmark 只准确率评分 DIM/DWD/DWS 的 `layer`；ODS、ADS 被目录角色固定，指标、实体、粒度只统计“有没有”，不比较语义是否正确。因此它目前是“中间层分类 benchmark”，不是完整“模型语义冷启动 benchmark”。
3. 18 张 DWS 中所有 `SUM`/`COUNT` 结果都被写成 `atomic_metrics`；按本仓库约定，聚合结果通常应是 derived metric。直接作为 gold 会奖励错误的指标分类。
4. ADS 中 10 张名为 `monitor`，但只有 DWS 字段透传和简单平均值，没有阈值、异常标志、待处理量、比率或状态判断；名称夸大了应用语义。
5. 现有 gold 没有结构化记录 business date、reversal policy、币种来源、正负号规则、可加性和允许汇总维度，无法可靠评价金融指标语义。

## DWS 逐表复核

| 表 | 结论 | business date / grain / 指标与修订意见 |
|---|---|---|
| `dws_account_transfer_transaction_daily` | Revise | `transaction_date` 正确；但按 `account_transfer_details_id` 分组接近划转头粒度，通常 `record_count=1`，不是真正有复用价值的日汇总。建议改为机构、账户类型、方向、币种、状态粒度，或明确命名为 transfer-detail daily fact。`is_reversed=false` 正确。 |
| `dws_cashier_transaction_daily` | Accept | `txn_date` 是业务日；`cashier_id + currency_code + txn_type` 粒度清楚，金额按币种和类型隔离，可加。源表无 reversal 字段，不能虚构冲正过滤；需在 gold 中注明该事实。 |
| `dws_client_transaction_daily` | Revise | 日期、客户/机构/币种/类型粒度和 `is_reversed=false` 均合理；但 `customer_management` 把资金事件归入客户主数据管理，建议使用独立 `client_transaction`/`customer_funds_transaction` 过程。 |
| `dws_collection_action_daily` | Accept | `start_date` 表示催收动作开始事件，`loan_id + action` 粒度合理，只有事件数，无金额可加性风险。应明确它只统计动作开始，不代表当日存量催收案件。 |
| `dws_deposit_hold_event_daily` | Revise | `transaction_date` 和 reversal 处理合理；账户是单币种，因此未显式带币种仍可解释，但 gold 应记录币种来自 savings account。`dpst_management` 不在过程目录，需改成有效过程代码。 |
| `dws_deposit_transaction_daily` | Accept | 交易日、机构/账户/类型粒度合理，`is_reversed=false` 与 Fineract 常用报表口径一致。`amount` 与 overdraft component 可在账户/类型内汇总；跨交易类型汇总前必须定义方向和正负号。 |
| `dws_gl_journal_posting_daily` | Accept | `entry_date` 是入账日，机构/科目/币种/借贷类型粒度正确，排除 reversed 分录。`total_amount` 只能在 debit/credit 类型内直接可加；跨类型应按借贷符号转换或分别比较，gold 必须声明。 |
| `dws_loan_delinquency_event_daily` | Revise | 只按 `addedon_date` 统计进入逾期档位，完全忽略 `liftedon_date`。`event` 名称暗示进入和解除两类事件；应改名为 delinquency-entry，或展开 `ENTER/LIFT` 事件类型。 |
| `dws_loan_disbursement_daily` | Accept | `disbursedon_date` 正确，分笔放款可按贷款日汇总，排除 reversed。贷款本身单币种，币种可由 loan account 继承；gold 应显式登记 currency source。 |
| `dws_loan_installment_charge_due_daily` | Revise | `due_date` 是合同到期日，但 paid/waived/written-off/outstanding 是当前可变状态；按历史 due date 回填会产生 hindsight，不能解释为“当日发生额”。应命名为 current schedule by due date，或引入 snapshot date 并把余额标为 semi-additive。 |
| `dws_loan_installment_due_daily` | Accept | `duedate + loan_id` 是还款计划到期桶，计划本金/利息/费用/罚息可按到期日汇总。它是 contractual schedule，不是实际还款流量；当前表名已包含 `due`，ADS 名称也基本吻合。 |
| `dws_loan_ownership_transfer_daily` | Revise | `settlement_date` 可以作为结算事件日，但 `status` 是当前可变状态，历史结算日会被后续状态覆盖。应筛选已结算状态，或引入状态快照/状态变更事件。按 loan 粒度的 count 也接近 1。 |
| `dws_loan_provision_entry_daily` | Revise | `provision_date` 实际由 provisioning run 的 `created_date` 派生，是运行创建日，不是明确定义的风险计量/拨备基准日。应改名为 run_date，保留 run/history id，并修正 Fineract 原字段拼写 `reseve_amount` 的展示名。拨备金额按币种隔离是正确的。 |
| `dws_loan_transaction_daily` | Accept | 交易日、机构/贷款/类型粒度合理，排除 reversed。金额和本金/利息/费用/罚息 components 可在类型内加总；跨交易类型必须有 sign convention。贷款币种由 loan account 继承。 |
| `dws_office_cash_transfer_daily` | Accept | `transaction_date`、from/to office、币种粒度合理，金额可加。源表没有 reversal/status 字段，gold 应说明这是记录的机构资金移动而非完成状态监控。 |
| `dws_share_transaction_daily` | Accept | 交易日、账户、类型、状态粒度清楚，以 `is_active=true` 作为有效记录口径合理。金额由 share account/product 继承币种；shares 与 currency amount 是不同 unit，不能混合评价。 |
| `dws_wc_breach_event_daily` | Revise | `start_date` 只表示 breach action 开始，未处理 `end_date`；建议命名 breach-start 或展开 START/END 事件。`wcln_management` 不在过程目录。 |
| `dws_wc_loan_transaction_daily` | Accept | 交易日、WC loan、交易类型粒度合理，排除 reversed。币种由 WC loan 继承；跨类型汇总仍需正负号约定。 |

### DWS 横向问题

- 18 张表的 `COUNT`/`SUM` 产物均列在 `atomic_metrics`，建议统一改成 `derived_metrics`，源明细金额才是 atomic measure。
- `TYPE`、`STATUS`、`ACTION`、`JOURNAL_ENTRY_CREATED` 被建模为 foreign entity；它们更适合作为 degenerate/code dimensions，不应与客户、账户、机构等业务实体混为一类。
- 每张表应在 gold 中给出 `metric.unit`、`currency_source`、`aggregation_behavior`、`additive_over`、`sign_convention` 和 `reversal_policy`。
- 所有作业目前全量重算；带 `daily` 的表是按业务日期分组，不是按日增量快照。gold 不应把 materialization strategy 和业务时间语义混为一谈。

## ADS 逐表复核

| 表 | 结论 | 应用计算与修订意见 |
|---|---|---|
| `ads_branch_cash_transfer_daily` | Accept | 在机构间划转日汇总上增加平均划转金额，表名未夸大为监控；业务应用虽薄但自洽。 |
| `ads_cashier_operation_daily` | Accept | 按柜员/币种/类型提供笔数、总额和平均额，可直接用于柜员运营看板。 |
| `ads_customer_transaction_monitor_daily` | Revise | 只有平均交易额，没有阈值、异常标志、客户基线或监控规则；应去掉 `monitor`，或增加大额/频次/偏离度指标。不能声称 AML。 |
| `ads_deposit_hold_monitor_daily` | Revise | 平均冻结金额不足以构成 hold monitor；建议增加未释放冻结量、释放时长、超期标志和账户/客户风险聚合。 |
| `ads_deposit_transaction_monitor_daily` | Revise | 只有平均交易和平均 overdraft，没有异常/趋势/阈值。应改名 transaction KPI，或增加异常频次、净流入方向和 overdraft ratio。 |
| `ads_disbursement_monitor_daily` | Revise | 贷款粒度下平均值常接近/等于总值，应用增量很低。监控应包含 expected vs actual date/amount、未放款、超额或延迟标志。 |
| `ads_gl_posting_monitor_daily` | Revise | 平均分录金额不是总账监控。至少应提供 debit/credit balance、imbalance amount、unposted/reversed/manual-entry ratios；当前名称明显夸大。 |
| `ads_internal_transfer_monitor_daily` | Revise | DWS 已接近 transfer-detail 粒度，平均值通常退化为原金额。应调整 DWS 粒度并增加失败/冲正/大额/跨机构规则，或去掉 monitor。 |
| `ads_loan_transaction_monitor_daily` | Revise | 平均 transaction components 是 KPI，不是监控；建议增加类型方向、异常/冲正率、超额、component reconciliation 和趋势指标。 |
| `ads_provision_posting_monitor_daily` | Revise | `journal_entry_created` 可支持待记账监控，但当前仅把布尔字段当维度并算平均拨备。应增加 pending count/amount、posting ratio、age，且日期必须改为明确的 run date。 |
| `ads_repayment_schedule_daily` | Accept | 到期日贷款粒度的计划本金、利息、费罚和平均每期金额符合还款计划应用集市语义；需注明它不代表实际回款。 |
| `ads_share_transaction_monitor_daily` | Revise | 只有均值，无监控规则；应改名 share transaction KPI，或加入异常价格、无效状态、金额与 `shares * unit_price` 勾稽。 |
| `ads_wc_transaction_monitor_daily` | Revise | 只有平均交易额，未提供 WC loan limit utilization、breach、minimum payment、冲正或异常规则；名称夸大。 |

ADS models 还缺少 DWS 已有的 `data_domain`、`business_area`、`business_process`、entities、time column/period 以及继承的 atomic/derived metrics。作为 gold 时必须补齐，不能只保存 `calculated_metrics`。

## 完整层级映射复核

结构一致性检查通过：

- 277 个 source table 唯一且每个都有一个 ODS；映射中的 277 个 ODS、34 个 DIM、62 个 DWD、18 个 DWS、13 个 ADS 目标均存在。
- 映射状态为 96 `structural_reviewed`、173 `candidate`、8 `security_reviewed`；只有 96 个 reviewed source 生成直接 DIM/DWD，边界逻辑一致。
- DWS/ADS 的 18/13 条 source-to-target 链与实际 SQL 文件一致。

但以下内容不能直接作为 gold：

- 200/277 行的 `business_processes` 代码不属于 canonical catalog。必须先把过程目录和映射统一，再冻结 gold。
- `fineract_layer_mapping.yaml` 使用 domain code（如 `LOAN`），model YAML 使用 taxonomy id（如 `'04'`）。gold schema 应同时保存 `data_domain_id` 与 `data_domain_code`，避免把表示差异算成模型错误。
- `m_calendar -> dim_business_calendar` 语义过宽；Fineract 的该表是可重复会议/事件日历，不是标准日期维。建议改名 meeting/calendar event definition。
- `m_guarantor -> dim_guarantor` 有争议：源表带 `loan_id` 和大量担保人 PII，更接近贷款担保参与方/关系卫星，不是天然一致性维度。gold 应允许 DWD factless relation 或 DIM participant 两种可接受答案，并由业务裁决。
- `m_wc_loan_payment_allocation_rule -> DWD fact` 是按贷款配置的规则事实，table type 至少需要人工裁决，不能把当前生成结果当无争议真值。
- `m_loan`、`m_savings_account`、`m_share_account` 作为 DIM 是可行建模选择，但也可被合理建成 accumulating snapshot/account entity。gold 应记录 `allowed_alternatives`，不要用单一标签惩罚合理架构选择。

## Benchmark 泄漏与 blocker 清单

### Blocker

1. **评分范围不足**：现有 runner 将 ODS/ADS 作为固定 asset role，只对 DIM/DWD/DWS 做 layer accuracy；metrics/entities/grain 只有数量统计，没有 exact/F1 或语义等价评分。
2. **gold 标签未闭合**：200 行无效 business-process code；31 张汇总/应用表中 18 张需修订；DWS metric class 系统性错误。
3. **金融语义标签缺失**：没有 reversal、sign、currency、unit、flow/state、semi-additivity、as-of/event date 标签，无法判断模型给出的金额语义是否安全。
4. **单一答案问题**：账户、担保人、规则表等存在合理替代建模方式，当前评分没有 allowed alternatives/partial credit/adjudication rationale。

### 输入泄漏/难度偏低

- 临时项目仍按 `ods/ddl`、`mid/ddl`、`ads/ddl` 分目录；ODS/ADS 角色直接由路径提供，不是在测试模型推断。
- ODS 名去掉 `ods_` 后仍保留 `fineract_`，DWS/ADS 保留 `_daily`、`monitor` 等强提示；这是 named/assisted track 可以接受的信号，但不能称为 role-blind。
- `business_taxonomy.yaml` 的 `project_context`、data domains 和 business areas 会被复制，明确写出了覆盖主题及排除主题。该模式应命名为 taxonomy-assisted，而不是 zero-shot。
- 任务 SQL 的 passthrough、`GROUP BY`、average projection 是合理证据，但也让三层形态高度模板化；需要 non-template holdout 才能防止模型只学 SQL 形状。
- source models/mappings/catalog 没有复制进临时项目，这一点是正确的；但如果被测 agent 能读取整个原仓库，仍可直接访问 gold。正式 benchmark 必须把 input bundle 与 private gold 放在不同权限边界。

## 建议 gold schema

每张表至少包含：

```yaml
asset_id: opaque_stable_id
expected:
  layer: DWS
  table_type: aggregate_fact
  allowed_alternatives: []
  data_domain_id: "04"
  data_domain_code: LOAN
  business_area_code: LOAN
  business_process_codes: [loan_transaction]
  semantic_subject_code: null
  disposition: materialize
grain:
  columns: [stat_date, office_id, loan_id, transaction_type_enum]
  primary_entity: LOAN
  related_entities: [OFFICE]
  degenerate_dimensions: [transaction_type_enum]
time_semantics:
  business_date_column: stat_date
  kind: event_date
metrics:
  - name: total_amount
    class: derived
    formula: sum(amount)
    unit: currency
    currency_source: dim_loan_account.currency_code
    aggregation_behavior: additive
    additive_over: [date, office, loan]
    sign_convention: gross_by_transaction_type
    reversal_policy: exclude_is_reversed_true
sensitivity:
  table_level: internal
  restricted_columns: []
annotation:
  upstream_commit: 45d8e24f82c9c42c46a6762b24e102ad2c723824
  reviewers: [reviewer_a, reviewer_b]
  adjudication: accepted
  rationale: "..."
```

评分应包含 layer/table type accuracy、domain/process Macro-F1、entity/grain F1、metric class F1、公式规范化等价、sensitivity recall，以及金融硬规则错误数。漏掉 restricted 字段、跨币种直接 SUM、把余额当全维可加、冲正重复计入应作为 hard failure，而非普通扣分。

## 建议难度分层

1. **Named / taxonomy-assisted**：保留业务表字段名、DDL、FK、任务 SQL和 taxonomy；去掉 models/mappings/catalog gold。评价完整语义，作为开发集。
2. **Prefixless / role-blind**：去掉所有层前缀，DDL 与任务扁平放置，不通过目录固定 ODS/ADS；保留业务词和 FK/SQL。作为主要测试集。
3. **Partially obfuscated**：稳定替换表名和部分非关键字段名，保留 FK 图、类型、SQL 运算和少量业务描述。只评分可由输入识别的 layer/table type/grain/metric behavior；完全混淆后不应强行评分 business domain。
4. **Template holdout**：保留一组非生成模板 SQL（窗口、状态快照、事件展开、多源勾稽、SCD）作为隐藏集，避免模型只按 passthrough/GROUP BY/average 三种 SQL 形状分类。

## 发布门槛

在以下条件完成前，建议标记为 `benchmark_candidate`，不要标记 `gold_v1`：

- 修复 200 行 business-process catalog 闭集问题；
- 对本报告 18 张 Revise 表完成修订并再次双人复核；
- 把聚合指标从 atomic/derived/calculated 重新裁决；
- 增加金融指标行为标签与 allowed alternatives；
- runner 增加 exact/F1/公式等价评分，并提供 role-blind 输入打包；
- gold 由至少两名 reviewer 独立标注并记录 adjudication。
