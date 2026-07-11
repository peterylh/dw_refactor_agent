# Retail Banking DIM/DWD 人工语义复核

## 1. 复核结论

复核范围为 `warehouses/retail_banking` 中 34 张 DIM、62 张 DWD，以及对应的
`fineract_layer_mapping.yaml`、model YAML、DDL 和 task SQL。结论针对“是否可作为模型语义冷启动
benchmark 的 gold”，不是针对 SQL 是否能执行。

| 层级 | ACCEPT | REVISE | REJECT | 合计 |
|---|---:|---:|---:|---:|
| DIM | 19 | 14 | 1 | 34 |
| DWD | 18 | 38 | 6 | 62 |
| **合计** | **37** | **52** | **7** | **96** |

- `ACCEPT`：目标层、表类型、源表、核心粒度和业务语义成立；只需应用全局统一规范。
- `REVISE`：保留该分析对象有价值，但必须修改名称、粒度、过程、实体、业务日期、指标或加工逻辑后才能进入 gold。
- `REJECT`：当前目标概念或层级有实质错误，不能作为正样本；应删除、移层或用新模型替换。作为 benchmark 时可保留为 hard negative。

**结论：当前版本可以作为 benchmark 候选语料和负样本集，不能直接冻结为 `gold_v1`。**

## 2. Gold 冻结前的 blocker

1. **实体关系缺失。** 96 个 model 的 `entities` 都只有一个自动生成的主实体；源表实际存在大量
   客户、账户、机构、产品、员工、交易、会计科目等 FK，但没有一个 model 声明外键实体或角色。
   这会让 entity/grain 评测退化为“把表名转成大写”。
2. **业务过程目录失配。** 62 个 DWD 中有 25 个使用不存在于 `business_processes.yaml` 的代码：
   `loan_management`、`dpst_management`、`fina_management`、`cust_management`、
   `paym_management`、`orgn_management`、`wcln_management`。这些不能作为 gold 标签。
3. **95/96 个任务没有真正的语义加工。** 87 个任务是单源字段直拷；8 个任务虽然做了 LEFT JOIN，
   但不投影被连接表字段，只产生无效的参照连接；只有 `dwd_loan_provision_entry` 真正从 run header
   补入了业务字段。大量目标表目前只是误导性改名复制。
4. **没有业务日期元数据。** 96 个 model 均未声明 event/effective/snapshot date。很多明细子表本身没有
   日期，必须从父交易、批次或 payout header 继承，否则无法可靠做时间切片和时序语义评测。
5. **账户维度混入余额事实。** `dim_loan_account`、`dim_deposit_account`、`dim_share_account` 和
   `dim_wc_loan_account` 直接复制当前状态及大量余额/累计金额，既没有 SCD，也没有账户日快照，维度与事实
   边界不清晰。
6. **7 个当前正样本应撤销。** `dim_guarantor`、`dwd_credit_report`、`dwd_customer_identifier`、
   `dwd_loan_interest_recalculation`、`dwd_loan_rate_period`、`dwd_wc_loan_lock_event`、
   `dwd_wc_payment_allocation_rule` 不应以当前层级/表类型进入 gold。

## 3. DIM 逐表审查清单（34）

| 目标表 | 源表 | Verdict | 人工复核意见 |
|---|---|---|---|
| `dim_accounting_rule` | `acc_accounting_rule` | ACCEPT | 会计规则配置维度成立，粒度为 rule id；关联实体应补 office、debit GL、credit GL。 |
| `dim_address` | `m_address` | ACCEPT | 地址主数据成立，粒度为 address id；country/state 是 code-value 角色实体，PII 分类需提升。 |
| `dim_asset_owner` | `m_external_asset_owner` | ACCEPT | 外部资产持有人主数据成立，粒度为 owner id；应补创建/修改用户审计实体。 |
| `dim_business_calendar` | `m_calendar` | REVISE | 源表是会议/活动日历与 recurrence，不是通用银行营业日历；改名为 meeting/event calendar，并关联 group/meeting 关系。 |
| `dim_charge_type` | `m_charge` | REVISE | 源对象是收费/罚金定义而非简单 type；建议 `dim_charge_definition`，补 tax group、payment type、GL account 角色。 |
| `dim_code_value` | `m_code_value` | REVISE | 单独 id 粒度物理正确，但业务键必须包含 `code_id + code_value`，并关联 `m_code` 形成代码集上下文。 |
| `dim_collateral` | `m_collateral_management` | REVISE | 源表是抵押品类别/估值模板，不是客户实际抵押物；建议 `dim_collateral_type`，实际抵押物来自 `m_client_collateral_management`。 |
| `dim_credit_bureau` | `m_creditbureau` | ACCEPT | 征信机构参考维成立；`m_creditreport` 只能作为受限文档/事件关联，不能反向混入此维。 |
| `dim_currency` | `m_currency` | ACCEPT | 币种参考维成立，业务键应为 currency code。 |
| `dim_customer` | `m_client` | REVISE | 客户一致性维成立，但必须做 SCD/有效期、PII 字段分级和当前状态定义；不能仅 full replace。 |
| `dim_customer_group` | `m_group` | REVISE | 团体/中心层级实体成立，但需 SCD、parent group、office、staff 等角色实体。 |
| `dim_customer_group_level` | `m_group_level` | ACCEPT | 团体层级参考维成立，补 parent-level 自关联即可。 |
| `dim_delinquency_bucket` | `m_delinquency_bucket` | ACCEPT | 逾期桶定义维度成立；应和 delinquency ranges 建层级关系。 |
| `dim_delinquency_range` | `m_delinquency_range` | ACCEPT | 逾期区间参考维成立，明确 day range 的边界语义。 |
| `dim_deposit_account` | `m_savings_account` | REVISE | 账户主实体成立，但源表含余额、累计利息、透支和生命周期状态；DIM 只留耐久属性，金额进入账户日快照/累计事实。 |
| `dim_deposit_product` | `m_savings_product` | ACCEPT | 存款产品维成立；应关联 tax group、currency/计息规则等角色实体。 |
| `dim_gl_account` | `acc_gl_account` | ACCEPT | 总账科目维成立，补 parent account、tag/code value 及科目层级。 |
| `dim_guarantor` | `m_guarantor` | REJECT | 该源表是 loan-specific 担保人副本，含 loan_id、个人姓名地址和 entity_id，不是去重的一致性参与方；应转成受限的 loan-guarantor relation/party satellite。 |
| `dim_holiday` | `m_holiday` | ACCEPT | 节假日规则维成立；适用机构由 `m_holiday_office` bridge 表达。 |
| `dim_loan_account` | `m_loan` | REVISE | 贷款账户耐久维可保留，但当前复制了大量余额、应计、已偿、减免、核销指标；需拆 DIM、账户当前快照与生命周期事件。 |
| `dim_loan_product` | `m_product_loan` | ACCEPT | 贷款产品维成立；产品参数很多，gold 应区分属性、规则实体和金额阈值。 |
| `dim_office` | `m_office` | ACCEPT | 机构维及 parent-office 层级成立，业务键可用 hierarchy/name 或 external id。 |
| `dim_payment_type` | `m_payment_type` | ACCEPT | 支付类型参考维成立。 |
| `dim_provision_category` | `m_provision_category` | ACCEPT | 拨备类别参考维成立，可与 criteria/range 规则关联。 |
| `dim_rate` | `m_rate` | REVISE | rate definition 成立，但百分比有时间/审批语义；需定义 SCD/effective date，避免把当前百分比当永久属性。 |
| `dim_rate_index` | `m_floating_rates` | REVISE | 这里只是浮息指数 header；实际时点利率在 period 表。应构建 index 维 + rate observation fact，而非把 header 当完整利率维。 |
| `dim_share_account` | `m_share_account` | REVISE | 股份账户主实体成立，但批准份额、购买份额、状态日期等应拆账户维、事件和快照事实。 |
| `dim_share_product` | `m_share_product` | ACCEPT | 股份产品维成立，市场价格应由独立时点事实承载。 |
| `dim_staff` | `m_staff` | REVISE | 员工维成立，但 office/active 状态会变化，应 SCD；同时与历史 staff assignment 明确边界。 |
| `dim_survey` | `m_surveys` | ACCEPT | 调查问卷 header 维成立；问题、选项和响应需作为下级实体/事实补齐。 |
| `dim_teller` | `m_tellers` | REVISE | 柜台/出纳点主数据成立，但有 valid-from 与 office/借贷科目关系，应做有效期维度。 |
| `dim_wc_loan_account` | `m_wc_loan` | REVISE | 营运资金贷款账户实体成立，但状态、额度、余额和 breach 指标混在源表；按账户维 + 日快照/事件拆分。 |
| `dim_wc_loan_product` | `m_wc_loan_product` | ACCEPT | 营运资金贷款产品维成立，补 fund、delinquency bucket、breach configuration 角色。 |
| `dim_working_day_rule` | `m_working_days` | ACCEPT | 系统级工作日/还款顺延规则可作为单行规则维；需注明 singleton scope，而非普通实体维。 |

## 4. DWD 逐表审查清单（62）

| 目标表 | 源表 | Verdict | 推荐业务日期 | 人工复核意见 |
|---|---|---|---|---|
| `dwd_account_transfer` | `m_account_transfer_details` | REVISE | 无/由交易继承 | 这是转账 header/参与账户关系，不是交易事件；建议 transfer instruction/bridge 类型，主实体为 transfer，外键角色含 from/to office、client、loan、savings account。 |
| `dwd_account_transfer_transaction` | `m_account_transfer_transaction` | ACCEPT | `transaction_date` | 转账交易事件成立，id 粒度正确；补 transfer header、from/to loan/savings transaction 角色。 |
| `dwd_asset_owner_gl_relation` | `m_external_asset_owner_journal_entry_mapping` | REVISE | GL `entry_date` | 是 owner 与 journal entry 的 bridge，不是普通数值事实；过程应为 loan asset transfer/GL mapping，业务日期从 journal entry 继承。 |
| `dwd_cashier_transaction` | `m_cashier_transactions` | ACCEPT | `txn_date` | 柜员现金交易事实成立，粒度为 cashier transaction id，补 cashier/teller/office 角色。 |
| `dwd_client_charge` | `m_client_charge` | REVISE | `charge_due_date` | 是客户收费应收的 accumulating snapshot，不是笼统 customer management；需定义 assessed/paid/waived/write-off/outstanding 指标状态。 |
| `dwd_client_charge_allocation` | `m_client_charge_paid_by` | REVISE | parent transaction date | 付款交易到客户费用的分摊事实成立，但必须关联 parent client transaction 获取日期，grain 为 transaction-charge allocation。 |
| `dwd_client_transaction` | `m_client_transaction` | ACCEPT | `transaction_date` | 客户级资金交易事实成立，明确 transaction type、reversal 和 client 角色。 |
| `dwd_collection_action` | `m_loan_delinquency_action` | ACCEPT | `start_date` | 催收/逾期动作区间事实成立；`end_date` 为关闭日期，loan 为核心外键实体。 |
| `dwd_credit_report` | `m_creditreport` | REJECT | 无可靠日期 | 包含 `national_id` 和完整 report payload，只有征信机构 FK，没有客户键/拉取时间；不应作为普通 DWD 正样本。改为受限 document vault + 脱敏征信查询事件。 |
| `dwd_customer_address_relation` | `m_client_address` | REVISE | effective date 缺失 | 是 customer-address-type bridge，table_type 应为 bridge/factless relation，不应标普通 fact；当前源表无有效期。 |
| `dwd_customer_identifier` | `m_client_identifier` | REJECT | creation/effective date | 身份证件是客户 PII satellite/多值维，不是业务事实；应移到受限 DIM satellite，并建立脱敏策略。 |
| `dwd_customer_transfer_event` | `m_client_transfer_details` | ACCEPT | `proposed_transfer_date` | 客户跨机构转移 accumulating event 成立；补 from/to office、submitter、状态日期语义。 |
| `dwd_deposit_charge` | `m_savings_account_charge` | REVISE | `charge_due_date` | 存款费用应收 accumulating snapshot 成立；过程应新增 deposit charge assessment/settlement，而不是不存在的 `dpst_management`。 |
| `dwd_deposit_charge_allocation` | `m_savings_account_charge_paid_by` | REVISE | parent transaction date | 存款交易到费用的分摊事实；需从 savings transaction 继承日期，明确 transaction-charge grain。 |
| `dwd_deposit_hold_event` | `m_deposit_account_on_hold_transaction` | REVISE | `transaction_date` | 冻结/解冻事件成立，但过程代码无效；应新增 deposit hold process，并声明 deposit account、creator 和 reversal 语义。 |
| `dwd_deposit_officer_assignment` | `m_savings_officer_assignment_history` | REVISE | `start_date` | 账户经理分配区间事实成立，但过程代码无效；grain 应为 account-officer-effective interval。 |
| `dwd_deposit_transaction` | `m_savings_account_transaction` | ACCEPT | `transaction_date` | 核心存款交易事实成立，含 amount/reversal/running balance；关联存款账户、机构、支付明细。 |
| `dwd_deposit_transaction_tax` | `m_savings_account_transaction_tax_details` | REVISE | parent transaction date | 税明细必须继承 savings transaction 日期，grain 为 transaction-tax component；当前直拷缺业务时间。 |
| `dwd_gl_close_event` | `acc_gl_closure` | REVISE | `closing_date` | 关账事件成立，但过程应为 `general_ledger_posting` 或新增 GL period close，不能用不存在的 `fina_management`。 |
| `dwd_gl_journal_entry` | `acc_gl_journal_entry` | ACCEPT | `entry_date` | 总账分录事实成立，粒度为 journal line id；transaction_id 是凭证粒度，必须保留借贷 type、GL account、office 和源交易角色。 |
| `dwd_group_customer_relation` | `m_group_client` | REVISE | effective date 缺失 | 复合粒度 `group_id + client_id` 正确，但 table_type 应是 bridge；需要关系有效期或快照日期。 |
| `dwd_group_meeting_attendance` | `m_client_attendance` | REVISE | meeting/calendar date | 到会事实成立，但源表只有 meeting id，无日期；必须关联 meeting/calendar 得到会议日期，实体为 group meeting + client。 |
| `dwd_group_role_relation` | `m_group_roles` | REVISE | effective date 缺失 | 是 group-client-role bridge，不是普通 fact；过程代码 `cust_management` 无效。 |
| `dwd_guarantee_commitment` | `m_guarantor_funding_details` | REVISE | snapshot/effective date 缺失 | 是担保资金承诺的当前累计状态，金额字段成立但缺业务日期；关联 guarantor 与 portfolio account association，过程应为 `guarantee_management`。 |
| `dwd_guarantee_transaction` | `m_guarantor_transaction` | REVISE | loan/deposit transaction date | 源表本质是 guarantor funding、loan transaction、hold transaction 的三方 bridge，无自身金额/日期；改 table_type 和继承日期。 |
| `dwd_loan_approval_event` | `m_loan_approved_amount_history` | REVISE | `created_on_utc` | 审批额度变更事件成立，但应新增 loan approval process，补 loan/user 角色，不能用 `loan_management`。 |
| `dwd_loan_charge` | `m_loan_charge` | REVISE | `due_for_collection_as_of_date` | 贷款费用 accumulating snapshot 成立；需独立 charge assessment/settlement process，并明确应收、已付、减免、核销、税金额。 |
| `dwd_loan_charge_allocation` | `m_loan_charge_paid_by` | REVISE | parent loan transaction date | 交易到 loan charge 的分摊事实；需继承交易日期，grain 为 transaction-charge allocation，过程改为 loan repayment/charge settlement。 |
| `dwd_loan_collateral_pledge` | `m_loan_collateral_management` | REVISE | pledge/effective date 缺失 | 是 loan 与 client collateral 的质押关系并带 quantity；过程应为 `collateral_management`，当前无有效日期且 `loan_management` 无效。 |
| `dwd_loan_delinquency_event` | `m_loan_delinquency_tag_history` | ACCEPT | `addedon_date` | 逾期标签区间事件成立，`liftedon_date` 为结束日期，关联 loan 与 delinquency range。 |
| `dwd_loan_disbursement` | `m_loan_disbursement_detail` | ACCEPT | `disbursedon_date` | 分笔放款事实成立，expected/actual date、principal、net disbursal 粒度清晰。 |
| `dwd_loan_installment` | `m_loan_repayment_schedule` | REVISE | `duedate` | 分期计划 accumulating snapshot 成立，但 metric gold 漏掉 penalty 与多项 paid/waived/outstanding 字段；grain 应表达 loan + installment/version，而非仅技术 id。 |
| `dwd_loan_installment_charge` | `m_loan_installment_charge` | REVISE | `due_date` | installment-charge bridge/应收事实；过程改为 loan charge/repayment，补 installment 与 loan transaction 语义。 |
| `dwd_loan_installment_version` | `m_loan_repayment_schedule_history` | REVISE | `duedate` | 是重排后的 schedule version snapshot；gold grain 应为 loan + reschedule request/version + installment，而非 id。 |
| `dwd_loan_interest_recalculation` | `m_loan_recalculation_details` | REJECT | 无事件日期 | 源表是一对一贷款计息重算配置，不是 recalculation event；应作为 loan terms satellite/配置维，当前名称和 fact 类型会误导模型。 |
| `dwd_loan_lifecycle_event` | `m_loan_status_change_history` | REVISE | `status_change_business_date` | 生命周期状态事件本身正确，但过程应新增 loan lifecycle，`loan_management` 不在目录；补 loan、old/new status 语义。 |
| `dwd_loan_officer_assignment` | `m_loan_officer_assignment_history` | REVISE | `start_date` | 贷款经理分配区间事实成立，过程代码无效；grain 为 loan-officer-effective interval。 |
| `dwd_loan_ownership_transfer` | `m_external_asset_owner_transfer` | ACCEPT | `effective_date_from` | 贷款资产出售/回购/转让 header 事实成立，关联 loan、owner、previous owner，settlement 为补充日期。 |
| `dwd_loan_ownership_transfer_detail` | `m_external_asset_owner_transfer_details` | REVISE | transfer effective date | 是 transfer header 的余额明细，必须关联 `asset_owner_transfer_id` 继承日期和 owner/loan；当前直拷缺关键上下文。 |
| `dwd_loan_provision_entry` | `m_loanproduct_provisioning_entry` | REVISE | run `created_date` | run/entry 分离和 header enrichment 正确；但 gold 应把 `reseve_amount` 规范为 `reserve_amount`，声明 run、office、product、category、liability/expense GL 角色。 |
| `dwd_loan_provision_run` | `m_provisioning_history` | ACCEPT | `created_date` | 拨备批次/run header 事件成立；`journal_entry_created` 是状态而不是日期/指标，需关联 creator/modifier。 |
| `dwd_loan_rate_period` | `m_loan_rate` | REJECT | 无日期 | 源表只有 `(loan_id, rate_id)`，没有 period 起止；当前表名虚构了“期间”。应替换为 `bridge_loan_rate`，table_type=bridge。 |
| `dwd_loan_repayment_allocation` | `m_loan_transaction_repayment_schedule_mapping` | REVISE | parent transaction date | 还款交易到 installment 的本金/利息/费/罚分摊事实成立，但日期必须从 loan transaction 继承，grain 应表达 transaction + schedule。 |
| `dwd_loan_restructure_event` | `m_loan_reschedule_request` | ACCEPT | `submitted_on_date` | 重组申请 accumulating event 成立，另有 approve/reject 日期，关联 loan、reason 和操作用户。 |
| `dwd_loan_transaction` | `m_loan_transaction` | ACCEPT | `transaction_date` | 核心贷款交易事实成立，loan/office/payment detail、交易类型、冲正和各金额分量清晰。 |
| `dwd_loan_transaction_relation` | `m_loan_transaction_relation` | REVISE | from/to transaction date | 是交易与交易/charge 的 typed bridge，不是普通 fact；日期从关联交易继承。 |
| `dwd_office_cash_transfer` | `m_office_transaction` | REVISE | `transaction_date` | 机构间现金划转事实成立，但 `paym_management` 无效；建议 `cashier_operation` 或新增 office cash transfer process。 |
| `dwd_office_holiday_relation` | `m_holiday_office` | REVISE | holiday `from_date` | office-holiday bridge，复合 grain 正确；table_type 应为 bridge，过程不应使用不存在的 `orgn_management`。 |
| `dwd_product_gl_mapping` | `acc_product_mapping` | REVISE | effective/snapshot date 缺失 | 是产品/费用/支付类型到 GL account 的配置 bridge，不是交易事实；改 table_type、实体角色和 `general_ledger_posting`/accounting configuration 过程。 |
| `dwd_share_charge` | `m_share_account_charge` | REVISE | due/effective date 缺失 | 股份账户费用 accumulating snapshot 可保留，但源表缺明确日期；需定义快照日期及 assessed/paid/waived/write-off 语义。 |
| `dwd_share_charge_allocation` | `m_share_account_charge_paid_by` | REVISE | parent share transaction date | share transaction 到 charge 的分摊 bridge/fact，必须继承父交易日期。 |
| `dwd_share_dividend` | `m_share_account_dividend_details` | REVISE | payout header date | 当前只是 payout-to-account 明细，需连接 dividend payout header 获取日期和 product，才能称 dividend fact。 |
| `dwd_share_market_price` | `m_share_product_market_price` | REVISE | `from_date` | 时点价格事实成立，但 `share_value` 未被识别为 atomic metric；grain 应为 product + effective date，而非 id。 |
| `dwd_share_transaction` | `m_share_account_transactions` | ACCEPT | `transaction_date` | 股份账户交易事实成立，amount/share/charge 指标及 account 角色清晰。 |
| `dwd_staff_assignment` | `m_staff_assignment_history` | REVISE | `start_date` | 实际是 centre/group 与 staff 的有效期 assignment，不是普通组织事实；`orgn_management` 无效，需明确 centre 角色。 |
| `dwd_standing_instruction_event` | `m_account_transfer_standing_instructions_history` | ACCEPT | `execution_time` | 自动划转指令执行历史成立，status/amount/error 和 instruction 角色清晰。 |
| `dwd_survey_response` | `m_survey_scorecards` | ACCEPT | `created_on` | 客户问卷回答事实成立，实体应含 survey/question/response/user/client。 |
| `dwd_wc_breach_event` | `m_wc_loan_breach_action` | REVISE | `start_date` | 营运资金贷款 breach 区间事件成立，但 `wcln_management` 无效；应并入/细分 `delinquency_management`。 |
| `dwd_wc_loan_disbursement` | `m_wc_loan_disbursement_detail` | ACCEPT | `actual_disburse_date` | 营运资金贷款分笔放款事实成立，expected/actual amount 与 maturity date 清晰。 |
| `dwd_wc_loan_lock_event` | `m_wc_loan_account_locks` | REJECT | `lock_placed_on_cob_business_date` | 源表 PK 只有 loan_id，表示当前锁状态而非事件历史；不能命名 event。应做 loan lock snapshot/satellite，或另取审计事件源。 |
| `dwd_wc_loan_transaction` | `m_wc_loan_transaction` | ACCEPT | `transaction_date` | 营运资金贷款交易事实成立，含金额、类型、冲正、支付和分类角色。 |
| `dwd_wc_payment_allocation_rule` | `m_wc_loan_payment_allocation_rule` | REJECT | 无事件日期 | 源表是 loan-specific payment allocation 配置，不是业务事实；移至 rule/satellite，`wcln_management` 也不是合法过程。 |

## 5. 推荐的 gold_v1 修订顺序

1. 先撤销 7 个 REJECT 正样本，把它们放入 hard-negative 标签集，并定义替代模型。
2. 统一业务过程字典，删除 7 类自动拼接的 `*_management` 假代码；必要时补充
   `loan_lifecycle`、`loan_approval`、`charge_assessment`、`deposit_hold`、`office_cash_transfer` 等稳定过程。
3. 为每张表补 `primary entity + related entity roles + semantic grain + business date`，不能只复制 PK。
4. 将 4 张账户大宽 DIM 拆为耐久账户属性、状态历史和日快照；客户、机构、员工、产品等明确 SCD 策略。
5. 对无自身日期的 allocation/bridge/detail 表，连接 parent transaction/run/payout/header 继承业务日期和业务上下文。
6. 重做指标 gold：补齐 installment penalty/paid/waived/outstanding，识别 `share_value`，规范 `reseve_amount` 的语义别名。
7. 最终把 `ACCEPT/REVISE/REJECT`、修改前/后标签和理由同时保留，benchmark 才能评估模型是否能发现当前自动映射的错误，而不是只复现它。
