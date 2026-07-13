# Fineract → ODS / DIM / DWD / DWS / ADS 映射架构与生成门槛（独立审查）

## 1. 审查结论

Fineract 适合作为一个**贷款、储蓄和微型金融核心系统来源**，而不是完整的综合银行数据源。源码当前可检索到约 293 个唯一 `createTable` 名称，其中包含示例扩展表、租户控制表和运行时控制表；最终有效表还需要按 Liquibase changelog 顺序应用 rename/drop 后才能确定。仓库建设不能把“历史上出现过的唯一建表名数量”直接当成“当前应落 ODS 的表数量”。

推荐的总体原则是：

1. 对选定 Fineract 版本的**最终有效业务 schema** 做接近 1:1 的 ODS 镜像；控制、认证和框架表单独标为可选 ODS，不进入默认业务 DAG。
2. 每张 Fineract 表都必须在映射清单中出现，但不是每张表都必须产生独立 DIM/DWD/DWS/ADS。
3. DIM/DWD 按业务实体、事件和快照粒度合并建模；关联表、配置表、历史子表、支付分摊表通常作为一个事实/维度的组成来源。
4. DWS/ADS 只能由明确业务问题、可核验指标和可追踪粒度驱动，禁止按 ODS 表一对一生成。
5. 不从 Fineract 凭空生成银行卡、收单商户、ISO 20022 清算报文、资金交易、证券交易、完整 AML 案件、监管资本等主题。要建设这些主题，必须增加独立 ODS 源或明确标为 synthetic extension。

推荐的首期规模不是“280 ODS + 280 DWD”，而是：

| 层级 | 建议规模 | 说明 |
|---|---:|---|
| ODS | 约 260–290 | 以固定 Fineract tag 应用完 changelog 后的实际有效 schema 为准；框架/租户控制表可选 |
| DIM | 25–35 | 一致性维度、层级维度、产品和规则维度 |
| DWD | 55–80 | 业务事件、关系、明细事实、周期快照 |
| DWS | 30–45 | 客户、账户、贷款、机构、会计、风险主题日/月汇总 |
| ADS | 15–30 | 经营、资产质量、会计勾稽、催收、资金和运营应用 |
| 总计 | 约 385–480 | 表多但不靠空壳表凑数 |

## 2. Fineract 能力边界

### 2.1 可由 Fineract 直接支撑的核心域

- 客户、家庭成员、团体、中心/层级、客户身份标识和地址。
- 机构、员工、柜员、现金箱、营业日、节假日和工作日。
- 贷款产品、贷款账户、申请/审批/放款、还款计划、贷款交易、费用、利率重算、展期/重组、逾期、核销相关状态。
- 储蓄/定期/定额存款产品与账户、账户交易、利息、费用、冻结、受益人和账户划转。
- 担保人、担保资金、抵押品和抵押品管理。
- 总账科目、产品会计映射、会计分录、会计关账、试算平衡和分录汇总。
- 减值准备/拨备规则、逾期区间和贷款资产质量。
- 股份产品/股份账户。
- 贷款资产所有权和投资者转让。
- working-capital loan 模块（若部署启用）。
- 收费、税、浮动利率、调查、通知、外部事件和运行审计。

### 2.2 不能由纯 Fineract 直接证明的域

以下域不应仅凭名称或随机数据伪造为“Fineract 下游”：

| 缺失域 | 缺少的真实源事实 | 正确处理 |
|---|---|---|
| 银行卡 | 卡、授权、清算、拒付、卡生命周期 | 增加 card processor ODS |
| 商户收单 | 商户、终端、MCC、清算、结算批次 | 增加 acquiring ODS |
| 支付网络 | ISO 20022/ACH/SWIFT 原始消息和状态回执 | 增加 payment hub ODS |
| 资金与市场风险 | 债券、外汇、衍生品、交易台、估值曲线 | 增加 treasury/trading ODS |
| 证券托管 | 持仓、公司行动、结算指令 | 增加 securities ODS |
| 完整 AML/KYC | 名单筛查、交易监控命中、案件、调查、SAR | Fineract 客户/交易可作为输入，但需 AML 引擎 ODS |
| 监管资本 | RWA、资本工具、监管调整项 | 增加监管/风险计算源 |
| 信贷申请全流程 | 完整申请材料、评分特征、规则决策轨迹 | 现有 credit bureau 表只能覆盖部分输入 |

因此 ADS 可以建设“基于 Fineract 可观测事实的异常交易线索”，但不能命名为完整 AML 案件或监管报送事实。

## 3. 映射清单的数据契约

建议完整清单使用机器可读 YAML/CSV，至少包含以下字段：

```yaml
source:
  release: <fixed-fineract-tag-or-commit>
  module: loan
  table: m_loan_transaction
  source_kind: transaction
  status: active
  optional_module: false
domain:
  code: lending
  subdomain: loan_transaction
  business_object: loan
  business_processes: [loan_disbursement, loan_repayment, loan_adjustment]
mapping:
  ods_table: ods_m_loan_transaction
  disposition: component_source
  targets:
    - table: dwd_loan_transaction
      role: primary
    - table: dwd_loan_repayment_allocation
      role: enrich
  reason: transaction type is normalized into one canonical event fact
grain:
  source: one row per Fineract loan transaction record
  target: one row per non-reversed canonical loan transaction
keys:
  source_pk: [id]
  business_keys: [loan_id, id]
  foreign_keys: [loan_id, payment_detail_id, office_id]
loading:
  strategy: incremental_restate
  watermark: last_modified_date
  business_date: transaction_date
  restatement_window_days: 7
history:
  strategy: immutable_event_with_reversal
quality:
  rules: [pk_unique, fk_loan_exists, amount_nonnegative, reconciliation_to_gl]
governance:
  contains_pii: false
  owner: lending
  confidence: reviewed
  rationale_ref: FINERACT-LOAN-TRANSACTION
```

`disposition` 必须是下面的有限枚举：

- `standalone_dimension`：独立一致性维度。
- `standalone_fact`：独立事件/明细事实。
- `snapshot_source`：参与周期快照，不独立生成一张 DWD 明细。
- `component_source`：并入某个 DIM/DWD 的组成来源。
- `bridge_source`：生成多对多桥表。
- `rule_reference`：规则/码表，作为维度属性或计算输入。
- `operational_only`：只留 ODS，默认不进业务下游。
- `security_excluded`：认证令牌、密码等敏感控制表，不进入分析仓或只保留去敏运维指标。
- `unsupported_or_example`：示例/非标准扩展，默认排除。
- `optional_module`：模块未启用时不生成实体数据，下游必须可裁剪。

完整性要求是“100% 源表有 disposition 和理由”，不是“100% 源表有独立下游表”。

## 4. 核心业务域映射矩阵

下表给出批量映射的架构基准。实际清单应逐表继承这些规则，再用 override 处理例外。

### 4.1 客户、团体与关系

| Fineract 来源 | 建议下游 | 粒度/业务过程 | 历史和增量 |
|---|---|---|---|
| `m_client`, `m_client_non_person`, `m_family_members` | `dim_customer`, `dim_customer_scd`, `dwd_customer_lifecycle_event` | 客户当前态；客户版本；注册/激活/关闭等状态事件 | 客户属性 SCD2；联系方式等敏感字段脱敏；状态变化从快照差分或审计事件生成 |
| `m_client_identifier` | `dwd_customer_identifier`, 或并入受限客户维度 | 一个客户身份标识 | SCD2/有效期；值哈希或掩码；禁止进入普通 ADS |
| `m_address`, `m_client_address` | `dim_address`, `bridge_customer_address` | 一个地址；客户-地址关系 | 地址 SCD1，关系按有效期 SCD2 |
| `m_group`, `m_group_level`, `m_group_client`, `m_group_roles` | `dim_customer_group`, `bridge_group_customer`, `bridge_group_role` | 一个团体；一段成员关系 | 团体 SCD2，关系有效期历史 |
| `m_client_transfer_details`, `m_entity_relation`, `m_entity_to_entity_mapping`, `m_entity_to_entity_access` | `dwd_customer_transfer_event`, `bridge_entity_relation` | 一次客户迁移；一段实体关系 | 事件增量；关系 SCD2 |
| `m_client_attendance`, `m_meeting`, `m_calendar_instance` | `dwd_group_meeting_attendance` | 客户在一次会议/日历实例中的出席 | 业务日期增量；允许迟到修订 |

建议 DWS/ADS：

- `dws_customer_daily_snapshot`：客户每日状态、账户数、贷款余额、存款余额、逾期余额；一客户一天。
- `dws_customer_relationship_monthly`：团体/家庭关系和产品持有；一客户一月。
- `ads_customer_portfolio_overview`：客户规模、活跃度、产品渗透和风险分层。
- `ads_customer_data_quality`：证件、地址、关系完整度；不能宣称为完整 KYC 合规结论。

### 4.2 机构、员工、柜员和日历

| Fineract 来源 | 建议下游 | 粒度/业务过程 | 历史和增量 |
|---|---|---|---|
| `m_office` | `dim_office` | 一个机构节点 | 父子层级和开业日 SCD2 |
| `m_staff`, `m_staff_assignment_history`, `m_loan_officer_assignment_history`, `m_savings_officer_assignment_history` | `dim_staff`, `bridge_staff_assignment`, `dwd_account_officer_assignment` | 一个员工；一次任职/账户经理分配 | 人员 SCD2；分配按有效期 |
| `m_tellers`, `m_cashiers`, `m_cashier_transactions`, `m_office_transaction` | `dim_teller`, `dwd_cashier_transaction`, `dwd_office_cash_transfer` | 一次柜员现金交易/机构资金划转 | 不可变事件；冲正独立记录 |
| `m_business_date`, `m_holiday`, `m_holiday_office`, `m_working_days` | `dim_date`, `dim_business_calendar` | 一个自然日/机构营业日 | 规则变化 SCD2；按日重算未来日历 |

建议 DWS/ADS：`dws_office_daily_operation`, `dws_cashier_daily_balance`, `dws_staff_portfolio_monthly`, `ads_branch_performance`, `ads_cash_reconciliation`。

### 4.3 产品、费率与通用规则

| Fineract 来源 | 建议下游 | 粒度/业务过程 | 历史和增量 |
|---|---|---|---|
| `m_product_loan` 及 `m_product_loan_*` | `dim_loan_product`, `bridge_loan_product_charge`, `dim_loan_allocation_rule` | 一个贷款产品版本/规则 | 产品配置 SCD2；规则按生效期 |
| `m_savings_product` 及 `m_savings_product_*` | `dim_deposit_product`, `bridge_deposit_product_charge` | 一个存款产品版本 | SCD2 |
| `m_deposit_product_*`, `m_interest_rate_chart`, `m_interest_rate_slab`, `m_interest_incentives` | `dim_interest_rate_plan`, `bridge_rate_slab` | 一个利率方案/阶梯 | 按生效期 SCD2，不单独为每张规则表造维度 |
| `m_floating_rates`, `m_floating_rates_periods`, `m_rate` | `dim_rate_index`, `dwd_rate_observation` | 一个指数；某日/期间的利率观测 | 指数 SCD2；观测追加/修订 |
| `m_charge`, `m_payment_type`, `m_currency`, `m_code`, `m_code_value`, `r_enum_value` | `dim_charge_type`, `dim_payment_type`, `dim_currency`, `dim_code_value` | 一个标准码或规则 | 小表全量覆盖/SCD1；关键业务码 SCD2 |

这些表大多是 `rule_reference` 或 `component_source`。禁止自动生成 `dws_*`，除非有明确统计问题。

### 4.4 贷款账户与生命周期

| Fineract 来源 | 建议下游 | 粒度/业务过程 | 历史和增量 |
|---|---|---|---|
| `m_loan` | `dim_loan_account`, `dwd_loan_lifecycle_event`, `dws_loan_daily_snapshot` | 一笔贷款当前态；一次状态变化；一贷款一天 | 当前态按 `last_modified_date`；维度 SCD2；快照按业务日重算 |
| `m_loan_status_change_history`, `m_loan_approved_amount_history` | 并入 `dwd_loan_lifecycle_event`/`dwd_loan_approval_event` | 一次状态/审批金额变化 | 不可变事件；同日多次保留序列 |
| `m_loan_disbursement_detail` | `dwd_loan_disbursement` | 一次计划/实际放款 tranche | 追加+更正；与 loan transaction 勾稽 |
| `m_loan_transaction`, `m_loan_transaction_relation` | `dwd_loan_transaction` | 一条贷款资金/会计语义交易 | 不可覆盖删除；reversal 独立表达；transaction type 标准化 |
| `m_loan_transaction_repayment_schedule_mapping` | `dwd_loan_repayment_allocation` | 一条交易到一期还款计划的分摊 | 交易和计划双键；按变动贷款重算 |
| `m_loan_repayment_schedule`, `m_loan_repayment_schedule_history` | `dwd_loan_installment`, `dwd_loan_installment_version` | 一笔贷款的一期计划/一个计划版本 | 当前计划分区覆盖；历史版本保留 |
| `m_loan_charge`, `m_loan_charge_paid_by`, `m_loan_installment_charge`, `m_loan_overdue_installment_charge`, `m_loan_charge_tax_details` | `dwd_loan_charge`, `dwd_loan_charge_allocation` | 一笔费用；一次费用支付/税分摊 | 费用 SCD/状态；支付分摊追加 |
| `m_loan_term_variations`, `m_loan_reschedule_request`, `m_loan_reschedule_request_term_variations_mapping`, `m_loan_reage_parameter`, `m_loan_reamortization_parameter`, `m_loan_topup` | `dwd_loan_restructure_event` | 一次重组/重定价/展期/追加申请 | 事件追加；批准和拒绝均保留 |
| `m_loan_rate`, `m_loan_recalculation_details`, `m_loan_interest_recalculation_additional_details` | `dwd_loan_rate_period`, `dwd_loan_interest_recalculation` | 一段贷款利率有效期/一次重算 | 有效期 SCD2；重算事件 |
| `m_loan_paid_in_advance`, `m_loan_buy_down_fee_balance`, `m_loan_capitalized_income_balance`, `m_loan_progressive_model` | 并入贷款快照或专用余额事实 | 一贷款一业务日/一模型版本 | `snapshot_source`，通常不逐源表建 DWD |
| `glim_accounts`, `gsim_accounts` | `bridge_group_loan_account`, `bridge_group_savings_account` | 团体/成员与贷款或储蓄账户的关系 | 关系有效期；不重复主账户金额 |
| `m_repayment_with_post_dated_checks` | `dwd_loan_repayment_instrument` | 一笔贷款还款承诺/远期支票工具 | 工具状态 SCD2，兑现/拒付应表达为事件；不能等同现金回款 |

建议 DWS/ADS：

- `dws_loan_daily_snapshot`：一贷款一日；本金、利息、费用、罚息、未到期、逾期、核销和状态。
- `dws_loan_vintage_monthly`：放款月份 × MOB × 产品 × 机构。
- `dws_loan_cashflow_daily`：机构/产品/币种/日期的放款、回款、冲正和费用。
- `dws_loan_repayment_performance_monthly`：一贷款一月的应还、实还、提前和逾期。
- `ads_loan_portfolio`, `ads_loan_vintage_analysis`, `ads_repayment_behavior`, `ads_loan_restructure_monitor`。

### 4.5 逾期、催收和拨备

| Fineract 来源 | 建议下游 | 粒度/业务过程 | 历史和增量 |
|---|---|---|---|
| `m_delinquency_range`, `m_delinquency_bucket`, `m_delinquency_bucket_mappings`, `m_delinquency_payment_rule` | `dim_delinquency_bucket`, `dim_delinquency_rule` | 一个逾期区间/规则版本 | SCD2 |
| `m_loan_arrears_aging` | 并入 `dws_loan_daily_snapshot`，必要时 `dwd_loan_arrears_snapshot` | 一贷款一计算时点 | 每日快照；禁止把当前缓存当完整历史 |
| `m_loan_delinquency_tag_history`, `m_loan_installment_delinquency_tag_history`, `m_loan_delinquency_action` | `dwd_loan_delinquency_event`, `dwd_collection_action` | 一次逾期标签变化/催收动作 | 追加事件，允许迟到 |
| `m_provision_category`, `m_provisioning_criteria*`, `m_loanproduct_provisioning_mapping` | `dim_provision_rule` | 一个拨备规则版本 | SCD2 |
| `m_provisioning_history`, `m_loanproduct_provisioning_entry` | `dwd_loan_provision_snapshot` | 一贷款/产品/机构在拨备计算日的结果 | 按计算批次不可变；重跑用 run id 区分 |

建议 DWS/ADS：`dws_asset_quality_daily`, `dws_collection_performance_monthly`, `dws_provisioning_monthly`, `ads_delinquency_migration`, `ads_collection_workbench`, `ads_provision_reconciliation`。

### 4.6 储蓄、定期/定额存款和账户流水

| Fineract 来源 | 建议下游 | 粒度/业务过程 | 历史和增量 |
|---|---|---|---|
| `m_savings_account`, `m_deposit_account_*`, `m_savings_account_interest_rate_*` | `dim_deposit_account`, `dwd_deposit_term_event`, `dws_deposit_account_daily_snapshot` | 一个账户版本；一次期限事件；一账户一天 | 账户 SCD2；快照按营业日 |
| `m_savings_account_transaction`, `m_savings_account_transaction_tax_details` | `dwd_deposit_transaction` | 一次账户交易（含冲正语义） | immutable event + reversal；税明细并入/子粒度 |
| `m_savings_account_charge`, `m_savings_account_charge_paid_by` | `dwd_deposit_charge`, `dwd_deposit_charge_allocation` | 一笔账户费用/支付分摊 | 状态变化+追加分摊 |
| `m_deposit_account_on_hold_transaction` | `dwd_deposit_hold_event` | 一次冻结、解冻或占用事件 | 事件追加；当前冻结余额由事件重建 |
| `m_savings_officer_assignment_history` | 并入 `dwd_account_officer_assignment` | 一段账户经理分配 | 有效期 |
| `m_selfservice_beneficiaries_tpt` | `dim_transfer_beneficiary`（敏感受限） | 一个客户受益人关系 | SCD2；账号脱敏 |
| `m_mandatory_savings_schedule` | `dwd_mandatory_savings_installment` | 一笔强制储蓄计划的一期应存安排 | 当前计划分区覆盖；若可追溯版本则保留版本，否则不得虚构历史 |

建议 DWS/ADS：`dws_deposit_account_daily_snapshot`, `dws_deposit_flow_daily`, `dws_deposit_retention_monthly`, `ads_deposit_portfolio`, `ads_dormant_account_monitor`, `ads_interest_expense_analysis`。

### 4.7 账户划转、支付细节与口袋账户

| Fineract 来源 | 建议下游 | 粒度/业务过程 | 历史和增量 |
|---|---|---|---|
| `m_account_transfer_details`, `m_account_transfer_transaction` | `dwd_account_transfer` | 一次逻辑划转/其底层交易腿 | 逻辑 transfer id 为主；交易腿桥接到贷款/存款交易 |
| `m_account_transfer_standing_instructions`, `*_history` | `dim_standing_instruction`, `dwd_standing_instruction_event` | 一个指令版本/一次执行或状态变化 | SCD2+事件 |
| `m_payment_detail`, `m_payment_type` | 并入各交易事实；`dim_payment_type` | 一笔交易的支付工具属性 | payment detail 不单独建通用事实，避免重复计数 |
| `m_pocket`, `m_pocket_accounts_mapping`, `m_portfolio_account_associations` | `dim_pocket`, `bridge_portfolio_account` | 一个逻辑口袋；账户关系 | SCD2/有效期关系 |
| `interop_identifier` | 受限 `bridge_account_interop_identifier` | 一个账户外部互操作标识 | SCD2；值哈希/脱敏 |

“账户划转”不等于外部支付清算。ADS 可以统计 Fineract 内部 transfer，但不能称为 ACH/SWIFT 清算成功率。

### 4.8 会计和总账

| Fineract 来源 | 建议下游 | 粒度/业务过程 | 历史和增量 |
|---|---|---|---|
| `acc_gl_account`, `acc_product_mapping`, `acc_gl_financial_activity_account` | `dim_gl_account`, `bridge_product_gl_mapping` | 一个科目版本；一段产品-科目映射 | SCD2 |
| `acc_gl_journal_entry` | `dwd_gl_journal_entry` | 一条借/贷分录行 | immutable line + reversal；原币和本位币（若源有）分别保留 |
| `acc_gl_closure` | `dwd_gl_close_event` | 一机构一次会计关账 | 事件追加；关账日后迟到分录报警 |
| `acc_accounting_rule`, `acc_rule_tags` | `dim_accounting_rule`, `bridge_accounting_rule_tag` | 一个会计规则版本 | SCD2 |
| `acc_gl_journal_entry_annual_summary`, `m_journal_entry_aggregation_*`, `m_trial_balance` | 校验/加速源；`dws_gl_balance_daily/monthly` | 科目 × 机构 × 币种 × 日/月 | 从分录主事实重算；源汇总只用于对账，不作为唯一真相 |

建议 DWS/ADS：`dws_gl_balance_daily`, `dws_gl_balance_monthly`, `dws_product_profitability_monthly`, `ads_trial_balance`, `ads_gl_subledger_reconciliation`, `ads_branch_profitability`。

必须建立贷款/存款子账到 GL 的可追踪关系；若 Fineract 字段无法提供逐笔桥接，则报告对账差额，不能伪造 100% 匹配。

### 4.9 担保、抵押品和信用报告

| Fineract 来源 | 建议下游 | 粒度/业务过程 | 历史和增量 |
|---|---|---|---|
| `m_guarantor`, `m_guarantor_funding_details`, `m_guarantor_transaction` | `dim_guarantor`, `dwd_guarantee_commitment`, `dwd_guarantee_transaction` | 一个担保方；一笔担保承诺；一次担保资金事件 | 担保人 SCD2；承诺有效期；交易追加 |
| `m_collateral_management`, `m_client_collateral_management`, `m_loan_collateral`, `m_loan_collateral_management` | `dim_collateral`, `bridge_customer_collateral`, `dwd_loan_collateral_pledge` | 一项抵押物；一次贷款质押关系 | 抵押物估值 SCD2/事件；质押关系有效期 |
| `m_creditbureau*`, `m_organisation_creditbureau`, `m_creditreport` | `dim_credit_bureau`, `dwd_credit_report_request/result` | 一次征信请求/报告响应 | 追加事件；原始报告敏感加密或只留摘要 |

建议 DWS/ADS：`dws_loan_collateral_daily`, `dws_guarantee_exposure_daily`, `ads_collateral_coverage`, `ads_credit_bureau_usage`。不能从这些表生成完整信用评分模型效果，除非有明确评分和结果字段。

### 4.10 费用、税和客户级交易

| Fineract 来源 | 建议下游 | 粒度/业务过程 | 历史和增量 |
|---|---|---|---|
| `m_client_charge`, `m_client_charge_paid_by`, `m_client_transaction` | `dwd_client_charge`, `dwd_client_transaction` | 一笔客户级费用/交易 | 事件+冲正 |
| `m_tax_component`, `m_tax_component_history`, `m_tax_group`, `m_tax_group_mappings` | `dim_tax_rule` | 一个税组件/税组版本 | SCD2 |
| 各产品/账户 `*_charge*`, `*_tax_details` | 对应贷款、储蓄、股份、WC 交易事实的子事实 | 费用/税分摊 | 不构造跨产品重复总事实；统一视图可在 DWS 做 union |

建议统一 `dws_fee_income_daily` 和 `dws_tax_collection_monthly`，来源必须携带 `source_product_type`、`source_account_id`、`source_transaction_id` 防止重复。

### 4.11 股份产品和股份账户

| Fineract 来源 | 建议下游 | 粒度/业务过程 | 历史和增量 |
|---|---|---|---|
| `m_share_product*` | `dim_share_product`, `dwd_share_market_price` | 一个产品版本/一次价格观测 | SCD2/追加观测 |
| `m_share_account`, `m_share_account_transactions` | `dim_share_account`, `dwd_share_transaction`, `dws_share_account_daily_snapshot` | 一个账户版本；一次交易；一账户一天 | SCD2/事件/快照 |
| `m_share_account_charge*`, `m_share_account_dividend_details`, `m_share_product_dividend_pay_out` | `dwd_share_charge`, `dwd_share_dividend` | 一笔费用或股息分配 | 追加+冲正 |

该域是 Fineract 股份账户，不应扩张解释为证券交易/托管。

### 4.12 投资者和贷款资产所有权

| Fineract 来源 | 建议下游 | 粒度/业务过程 | 历史和增量 |
|---|---|---|---|
| `m_external_asset_owner` | `dim_asset_owner` | 一个外部贷款资产所有人 | SCD2 |
| `m_external_asset_owner_transfer*`, `*_loan_mapping` | `dwd_loan_ownership_transfer` | 一贷款份额的一次出售/回购/转让 | 事件追加，保留前后 owner 和比例 |
| `m_external_asset_owner_journal_entry_mapping`, `*_transfer_journal_entry_mapping`, `m_journal_entry_aggregation_*` | `bridge_asset_transfer_gl_entry` | 转让事件到分录的映射 | bridge，不复制金额 |
| `m_external_asset_owner_loan_product_configurable_attributes` | 并入产品/owner 规则维度 | owner × 贷款产品配置 | SCD2 |

建议 DWS/ADS：`dws_investor_exposure_daily`, `dws_asset_transfer_monthly`, `ads_asset_owner_position`, `ads_asset_transfer_reconciliation`。

### 4.13 Working-capital loan（可选模块）

`m_wc_*` 是独立、可选的 working-capital loan 子域，不能无条件塞入普通 `m_loan` 粒度。建议：

- `dim_wc_loan_product`, `dim_wc_loan_account`。
- `dwd_wc_loan_transaction`, `dwd_wc_disbursement`, `dwd_wc_payment_allocation`, `dwd_wc_breach_event`, `dwd_wc_rate_change`。
- `dws_wc_loan_daily_snapshot`, `dws_wc_breach_daily`。
- `ads_wc_portfolio`, `ads_wc_breach_monitor`。

若要提供全贷款组合视图，在 DWS 建立统一语义 union，并保留 `loan_engine_type = STANDARD|WORKING_CAPITAL`，不要物理合并两个 DWD 事实而丢失各自字段。

### 4.14 调查、通知、营销和文档

| Fineract 来源 | 建议处理 | 原因 |
|---|---|---|
| `m_surveys`, `m_survey_*`, `ppi_*` | `dim_survey`, `dwd_survey_response`, `dws_survey_score` | 有明确问卷/响应粒度，可分析，但不是核心账务 |
| `sms_campaign`, `sms_messages_outbound`, `scheduled_email_*`, `notification_*` | `dim_campaign`, `dwd_customer_communication_event`, `dws_campaign_delivery_daily` | 只能分析发送/投递状态；没有响应事实时不能声称营销转化归因 |
| `m_document`, `m_import_document`, `m_image`, `m_note` | 默认 ODS；必要时 `dwd_entity_document_metadata`/`dwd_entity_note_event` | 只抽取元数据，禁止把二进制/正文泛化进入分析层 |
| `m_hook*`, `m_template*` | `operational_only` 或运维维度 | 不属于银行业务事实 |

### 4.15 平台、权限、调度、审计与租户控制

| Fineract 来源 | 默认 disposition | 处理要求 |
|---|---|---|
| `m_appuser*`, `m_role*`, `m_permission`, `m_password_validation_policy` | `security_excluded` | 需要运维审计时只生成去敏 `dim_application_user` 和权限变更事件，不复制密码材料 |
| `oauth_*`, `twofactor_*`, `m_tenant_oidc_config` | `security_excluded` | token、secret 不进入数仓；最多保留按日成功/失败统计且不能含 token |
| `m_portfolio_command_source`, `command`, `m_command`, `request_audit_table` | `operational_only`，可选 `dwd_api_command_audit` | 只用于运维审计；请求 payload 必须脱敏 |
| `job*`, `job_parameters`, `job_run_history`, `scheduler_detail`, `batch_custom_job_parameters` | `operational_only` | 可生成 `dwd_job_run`，但与银行业务 DAG 分离 |
| `m_batch_business_steps` | `operational_only` | COB 业务步骤配置，不是业务事件；运行结果应从独立作业运行事实获取 |
| `m_external_event`, `m_external_event_configuration` | 可选 `dwd_integration_event` / `operational_only` | 一次 outbox/integration event；二进制 payload 默认不入分析层，只保留类型、聚合根、状态和时间 |
| `c_configuration`, `c_cache`, `c_external_service*`, `m_field_configuration` | `operational_only` | 配置快照，不生成业务 DWS |
| `stretchy_*`, `rpt_sequence`, `m_adhoc`, `m_report_mailing_*` | `operational_only` | 报表定义/调度，不是报表事实 |
| `mix_taxonomy`, `mix_taxonomy_mapping`, `mix_xbrl_namespace` | `rule_reference` / 可选报告维度 | MIX/XBRL 分类和映射元数据，不是已报送的监管事实 |
| `tenants`, `tenant_server_connections`, `timezones` | 独立 tenant-store ODS | 连接串/密码字段必须剔除；单租户演示项目可完全排除 |
| `x_registered_table`, `x_table_column_code_mappings`, `m_entity_datatable_check` | `operational_only` | 动态 datatable 元数据；需要另做动态表发现，不可按固定表处理 |
| `acme_note_dummy` | `unsupported_or_example` | 示例扩展表，纯 Fineract 默认排除 |

## 5. 哪些表不应强制生成独立下游

以下规则应作为生成器的默认抑制规则：

1. **纯关联表**：`*_mapping`, `*_mappings`, `*_paid_by`, `*_relation`, `*_roles`, `*_charge` 中仅含双键和少量属性者，生成 bridge 或并入主事实，不自动一表一 DWD。
2. **历史伴随表**：`*_history` 若只是主实体 SCD 版本，合并进主维度/事实版本；只有独立业务事件语义才生成事件事实。
3. **规则表**：`*_configuration`, `*_criteria`, `*_rule`, `*_strategy`, `*_template` 默认生成规则维度或只留 ODS，不生成 DWS/ADS。
4. **缓存与预聚合**：`*_summary`, `*_balance`, `*_aggregation_*`, `m_trial_balance`, `m_loan_arrears_aging` 不能自动成为事实真相；从明细重算并用其对账。
5. **支付细节子表**：`m_payment_detail`、tax details、allocation mapping 属于交易子粒度；独立成表时必须声明分摊粒度，不能与主交易金额重复汇总。
6. **安全控制表**：OAuth、2FA、密码、OIDC、server connection 永不进入普通业务层。
7. **调度和报告定义**：job、scheduler、stretchy report、mailing 配置只用于运维分析。
8. **文档/图像/模板**：只留元数据或排除正文/二进制。
9. **枚举和代码表**：合并为有域隔离的 `dim_code_value` 或少量业务维度；不能为每张小码表建一个 DWS。
10. **可选模块表**：WC loan、investor、share、survey、MIX/XBRL 在模块未启用时整个分支裁剪；不得生成永久空表来制造规模。

## 6. SCD、事件和增量策略

### 6.1 分类规则

| 源类型 | 识别信号 | 目标模式 | 默认加载 |
|---|---|---|---|
| 主实体 | 单一 `id`，多描述/状态字段，被多个 FK 引用 | DIM SCD2 + 可选当前视图 | `last_modified_date` watermark；无修改时间则 hash diff |
| 业务事件 | `transaction_date`, `submitted_on_date`, `type_enum`, `amount` | DWD append/reversal event | 按创建/修改水位增量，业务日期分区；7–30 天重述窗口 |
| 关系 | 两个以上 FK，少量关系属性 | bridge 或 assignment event | 有有效期则 SCD2；否则全量 diff |
| 周期/余额 | `balance`, `outstanding`, `due`, `overdue` 且为当前缓存 | DWS periodic snapshot | 按业务日重算；不得将 load time 当业务日期 |
| 规则/配置 | `is_active`, 枚举、阈值、利率/区间 | rule DIM SCD2 | 小表全量快照 + hash diff |
| 预聚合 | `summary`, `aggregation`, `trial_balance` | reconciliation input | 不作为唯一来源 |
| 运行控制 | job/audit/config/token/report definition | ODS-only/operations mart | 与银行业务加工隔离 |

### 6.2 Fineract 特有注意点

- Fineract 的业务日期 `m_business_date` 与数据库时间不同。所有日快照、关账和逾期计算优先使用 business date。
- `transaction_date`、`submitted_on_date`、`created_date`、`last_modified_date` 含义不同，生成器不得只取第一个包含 `date` 的字段。
- reversed/adjusted 交易应保留原记录及冲正关系，不能在 ODS/DWD 物理删除。
- 贷款还款计划会重算；当前 schedule 和 schedule history 需要分开处理，不能简单 append 当前表造成重复。
- 缺少可靠 CDC 时，账户/贷款当前表采用“按变更时间增量 + 近期业务分区重述 + 每日控制总数”的混合策略。
- 所有金额保留源币种和高精度 decimal；不允许二进制浮点。
- 同一业务日内多次状态变化需要 sequence/technical timestamp，不能只用 `date` 去重。

## 7. 对账规则

### 7.1 每日硬门槛

以下检查失败应阻断正式生成或 shadow compare：

1. **主键完整性**：ODS/DWD 声明主键非空且唯一；事件事实重复率为 0。
2. **参照完整性**：核心 FK（loan→client/group、transaction→account、journal→GL account、schedule→loan）孤儿率为 0；可空 FK 只在源允许场景出现。
3. **贷款交易勾稽**：按贷款/币种/业务日的本金、利息、费用、罚息交易与贷款汇总字段差异在精度容差内。
4. **还款计划勾稽**：每期 principal/interest/fee/penalty 的 due、paid、waived、written-off、outstanding 关系闭合；重算版本不重复。
5. **存款余额恒等式**：期初 + 有效流入 − 有效流出 + 利息 − 费用/税 = 期末；冲正必须抵消原交易。
6. **借贷平衡**：按 journal transaction/office/currency/business date 的 debit = credit；不能只做全局平衡。
7. **子账–总账勾稽**：贷款和存款产品按 product mapping 汇总至 GL；不能映射的差额单列，不得静默归零。
8. **划转双腿平衡**：内部账户 transfer 的 debit/credit 腿数量、币种、金额和状态一致。
9. **逾期一致性**：days past due、bucket、overdue amount 与未偿还 schedule 一致；bucket 规则使用当日有效版本。
10. **拨备一致性**：拨备基数、比例和金额能回溯到贷款快照与规则版本。
11. **快照覆盖**：每个活跃账户/贷款在应有业务日至少一条快照；关闭账户按政策停止或保留零余额，规则统一。
12. **PII/secret 检查**：token、密码、连接串、未脱敏证件号不出现在非受限模型。

### 7.2 建议阈值

| 质量项 | 生成阶段门槛 | 日常运行门槛 |
|---|---:|---:|
| 源表映射覆盖率 | 100% | 100% |
| `unknown` disposition | 0 | 0 |
| 核心事实 grain/PK/业务日期声明率 | 100% | 100% |
| 核心 FK 孤儿率 | 0 | 0；源系统已存在脏数据时进入 quarantine 且单列 |
| 借贷不平衡金额 | 0 | 0 |
| 贷款/存款金额对账差异 | ≤ `0.01` 最小货币单位等效值，且记录原因 | 同左 |
| 事件重复率 | 0 | 0 |
| 关键日快照覆盖率 | 100% | ≥99.99%，缺失必须报警并补算 |
| 未声明 SCD/增量策略的 DIM/DWD | 0 | 0 |
| 无来源指标 | 0 | 0 |
| 非受限层发现 secret | 0 | 0 |

金额容差应按币种 decimal places 计算；不能全项目硬编码 `0.01`。

## 8. 可自动化生成的规则

### 8.1 两阶段生成，禁止一次性“猜表”

**阶段 A：源 schema 编译**

1. 固定 Fineract tag/commit 和数据库方言。
2. 从所有 master changelog 递归解析 include。
3. 依序应用 create/rename/drop/add/drop column 和模块条件，得到最终 schema；保留变更历史。
4. 区分 tenant schema、tenant-store schema、示例 extension 和可选模块。
5. 输出 `source_schema.json`：表、列、类型、PK、UK、FK、默认值、审计列、来源 changelog。

**阶段 B：语义映射编译**

1. 先按 module/path 分域，再按显式 override，最后才使用名称规则。
2. 计算表结构特征：FK 入度/出度、金额字段、日期字段、状态/枚举字段、行级审计字段。
3. 产生 disposition 建议和 confidence。
4. `confidence != reviewed`、多候选业务日期、无 PK、金额事实无币种、FK 环路进入人工队列。
5. 只有被批准的 mapping manifest 才能生成 DDL、tasks、models 和测试。

### 8.2 规则优先级

```text
manual table override
  > module-specific rule
  > exact-name rule
  > structural archetype rule
  > prefix/suffix heuristic
  > unknown (fail closed)
```

名称规则只能生成候选，不能自动确定事实粒度。例如 `*_history` 可能是 SCD 历史，也可能是业务事件；`*_balance` 可能是当前缓存，也可能是有业务日期的事实。

### 8.3 可安全批量生成的资产

- ODS DDL：源类型映射、PK/unique key 策略、审计列、稳定 schema identity。
- ODS 统一增加技术字段 `load_time DATETIME`；当前 execution 的自动日期发现会查询每张 ODS 的 `load_time`。首期仍建议显式传 `--etl-dates`，避免扫描数百张 ODS 做日期发现。
- ODS models YAML：名称、来源模块、敏感等级、物化和加载策略。
- DIM/DWD DDL 骨架：仅当 mapping 明确 grain、key、business date、disposition 和 target。
- SQL join 骨架：只使用已验证 FK；金额计算和业务状态解释必须来自显式规则。
- models YAML：layer、table_type、grain、entities、business_process、execution slice。
- 基础测试：PK、not-null、FK、accepted-values、金额精度、分区覆盖。
- 血缘和 DAG：从生成 SQL 解析，不从 mapping 声明伪造。

### 8.4 必须人工评审的资产

- 交易类型 enum 到业务过程的解释。
- 贷款本金/利息/费用/罚息的金额口径。
- reversed/rescheduled/re-aged/re-amortized 的会计和统计含义。
- schedule history 的版本选取。
- 产品到 GL 的会计映射与差额处理。
- 客户 SCD2 属性范围和 PII 策略。
- DWS 指标可加性、半可加性和汇率口径。
- ADS 的监管/风险含义和命名。

## 9. 生成资产的质量门（gates）

### Gate 0：来源固定

- 固定 commit/tag、许可证和上游来源 URL。
- 解析后的 active table 数与 inventory 清单一致。
- 所有 drop/rename 已应用；`acme_note_dummy` 等示例表有明确排除决定。

### Gate 1：映射完整

- 每张 active source table 有 domain、disposition、reason、owner、confidence。
- 100% 下游表有 source table/column lineage、grain、key、business date。
- 可选模块可整体开关，下游 DAG 无悬挂依赖。

### Gate 2：模型合理

- 一个 DIM 只表达一个稳定业务实体/规则实体。
- 一个 DWD 只表达一个可陈述粒度；混合 header/line 时必须拆分。
- DWS 不直接复制 ODS 当前余额作为“历史”。
- ADS 有消费场景、指标定义、过滤条件和刷新 SLA。
- 没有一表一 DWD 的机械镜像，也没有无消费者的空壳 DWS/ADS。

### Gate 3：SQL 可执行

- Doris DDL 通过 parser/数据库 dry run。
- 每个 task 有确定的 `@etl_date` 行为和幂等重跑策略。
- 日/月增量模型显式声明 `execution.slice`；当前 runner 支持的 period 以 `D/M/W/H` 为限，季度/年度应用应使用月切片或 full 物化。
- schema identity 全部初始化并验证。
- DAG 无环、层级依赖合法、命名规范通过。

### Gate 4：数据正确

- 固定随机种子造数满足 FK、业务状态机、会计平衡和跨表勾稽。
- 所有第 7 节硬门槛测试通过。
- 至少覆盖正常、冲正、提前还款、逾期、重组、核销、关闭、迟到数据和利率变更场景。

### Gate 5：重构验证

- `schema_ids validate` 通过。
- lineage 抽取无 unresolved table/column。
- `task_run` 全量与多日增量重跑一致。
- shadow run 的 count/row compare 通过；运行时间列按项目配置排除。
- 生成资产与手工 override 的 diff 可复现。

## 10. 建议的生成顺序

不要一次性生成 400 张表后才验证。建议按能闭环的纵向切片推进：

1. **基础维度**：currency/code/date/office/staff/client/product。
2. **贷款闭环**：loan → schedule → transaction → charge → daily snapshot → portfolio ADS。
3. **会计闭环**：GL account → journal → balance → subledger reconciliation。
4. **存款闭环**：savings account → transaction → charge/interest → daily snapshot。
5. **划转与柜面**：transfer/cashier/office transaction。
6. **逾期、催收、拨备**。
7. **担保、抵押、征信**。
8. **股份、投资者资产转让、working-capital optional modules**。
9. **调查、通信和运维 mart**。

每个切片先通过 Gate 0–5，再扩大到下一个域。这样能尽早暴露 Fineract 语义、Doris 方言和 `@etl_date` 重跑问题。

## 11. 最终审查意见

可以批量生成，但必须以一份**版本化、逐源表、带 disposition 的 mapping manifest**作为唯一输入。最重要的设计约束有三条：

1. “完整映射”是每张源表都有去向或排除理由，不是每张源表都强行生成独立下游。
2. 业务事件、关系、规则和缓存必须先分类，再决定 DIM/DWD/DWS/ADS；只靠表名前缀/后缀不足以安全生成。
3. 任何银行主题和指标必须能回溯到 Fineract 的真实字段与业务过程；纯 Fineract 不具备的卡、收单、支付网络、市场风险和完整 AML/监管能力必须明确留白或新增源系统。

在上述约束下，Fineract 能支撑一个规模大、DAG 深、对账复杂且适合当前重构验证框架的银行/微型金融数仓，同时避免把 280 余张 ODS 机械膨胀成低质量的 280 张 DWD。
