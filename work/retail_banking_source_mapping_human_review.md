# retail_banking Fineract 源表映射人工复核

## 结论

本轮按 `fineract_table_mapping.yaml` 的 277 个唯一 `source_table`，逐项关联
`fineract_schema_snapshot.yaml` 的列、PK/UK/FK、来源文件和当前映射字段完成复核。
277 张表均有且仅有一条 mapping，schema snapshot 与 mapping 无缺失、无重复。

当前清单适合作为“待标注集”，**不应原样冻结为模型语义冷启动 benchmark 的 gold_v1**。
确定性问题为 3 个 blocker、5 组 major、3 组 minor。最主要的问题不是表数，而是：

1. `security_excluded` 与 `confidence` 自相矛盾，并存在秘密/PII 漏标；
2. 账户主表被整体复制成 DIM，同时包含大量时变余额和累计金额；
3. 173 张表仍是 `candidate`，其中 `component_source` 实际没有进入任何下游；
4. 若干由表名关键词造成的数据域和事实/规则误判。

## 基线统计与范围口径

| 项目 | 数量 | 复核结论 |
|---|---:|---|
| Fineract 物理表 | 287 | 口径一致，但必须始终说明是固定 commit 下 tenant + tenant-store 的合计 |
| 分析租户应用表 / ODS | 277 | mapping 与 snapshot 一一对应 |
| 排除的 Spring Batch 表 | 6 | 合理，属于调度控制面 |
| 排除的 tenant-store 表 | 4 | 合理，属于多租户/连接/身份控制面 |
| 已生成直接 DIM/DWD | 96 | DIM 34、DWD 62 |
| candidate | 173 | 尚不能称人工 gold |
| security_reviewed | 8 | 少于 `security_excluded` 的 16，存在矛盾 |
| restricted | 34 | 存在确定性漏标 |

`287 = 277 + 6 + 4` 的算术和清单一致。更准确的对外表述应为：固定在 Fineract
commit `45d8e24f82c9c42c46a6762b24e102ad2c723824`，tenant 应用 schema 有 277 张分析表，
另有 6 张 tenant 内 Spring Batch 表及 4 张 tenant-store 控制表；不应脱离版本宣称
“所有版本纯 Fineract 恒定为 287 张表”。

## Blocker

### B1. security 状态自相矛盾

当前有 16 张 `security_excluded`，但只有 8 张 `confidence: security_reviewed`。
以下 8 张同时标成 `security_excluded` 和 `candidate`，对 benchmark 来说没有唯一真值：

- `job`
- `m_adhoc`
- `m_appuser_role`
- `m_command`
- `m_report_mailing_job`
- `scheduled_email_campaign`
- `scheduled_email_messages_outbound`
- `twofactor_configuration`

建议：逐表确认后统一改为 `security_reviewed`；如果某表只是运维元数据而非秘密载体，
则改成 `operational_only + human_reviewed_ods_only`，不能保留当前组合。

### B2. 确定性秘密和 PII 漏标

以下表当前为 `internal`，但列结构决定其至少应为 `restricted`；其中配置 value/JSON
还需要列级 secret 标注：

| 表 | 证据列 | 建议 |
|---|---|---|
| `c_external_service_properties` | `name`, `value` | restricted；secret value 不进入通用下游 |
| `m_creditbureau_configuration` | `configkey`, `value` | restricted/security-reviewed |
| `m_hook_configuration` | `field_name`, `field_value` | restricted；按 field_name 识别 credential |
| `m_report_mailing_job_configuration` | `name`, `value` | restricted；SMTP/邮件配置行需 secret |
| `scheduled_email_configuration` | `name`, `value` | restricted；SMTP credential 需 secret |
| `batch_custom_job_parameters` | `parameter_json` | restricted；任意 JSON 可能含凭据/PII |
| `job_parameters` | `parameter_name`, `parameter_value` | restricted |
| `m_portfolio_command_source` | `command_as_json`, `result`, `client_ip` | restricted/security-reviewed |
| `m_payment_detail` | `account_number`, `check_number`, `bank_number`, `routing_code` | restricted；仅脱敏字段下游 |
| `m_client_non_person` | `incorp_no` | restricted |
| `glim_accounts` | `account_number` | restricted |
| `gsim_accounts` | `account_number` | restricted |
| `m_note` | `note` 及客户/贷款外键 | restricted/free-text |
| `m_wc_loan_note` | `note` | restricted/free-text |
| `m_document` | `file_name`, `description`, `location` | restricted |
| `m_image` | `location` | restricted |
| `sms_campaign` | `param_value`, `message` | restricted（至少做内容扫描） |

这 17 张是结构证据即可确认的最低修正集，不包含仅凭业务猜测的表。

### B3. 表级 sensitivity 不足以作为安全 benchmark gold

12 张 restricted 源表已直接生成 DIM/DWD，包括 `m_client`、`m_address`、
`m_client_identifier`、`m_creditreport`、`m_guarantor`、`m_staff` 和四类账户主表。
当前映射没有 `column_sensitivity`、`allowed_downstream_columns`、`masking_action`，而生成任务会
原样复制客户姓名、手机号、邮箱、证件号、national id 和信用报告正文。若 benchmark 要评估
敏感字段识别，这一标签粒度无法形成可评分真值。建议在 gold_v1 前补齐列级标签及动作：
`drop/hash/tokenize/mask/pass_through`。

## Major

### M1. 四类账户主表不能只定义成普通 DIM

- `m_loan`
- `m_savings_account`
- `m_share_account`
- `m_wc_loan`

其中 `m_loan`、`m_savings_account` 明确包含本金、余额、应收、已还、逾期、费用、利息等大量
时变派生金额；当前 `dim_loan_account` / `dim_deposit_account` 全字段覆盖会把事实度量塞入 DIM。
建议一源多目标：稳定合同/账户属性进入 DIM，时变金额进入按业务日的账户快照 DWS/DWD。
`m_share_account` 也应按稳定属性与持仓状态拆分；`m_wc_loan` 同理。

### M2. 八张 snapshot_source 全部停在 candidate，遗漏了最有价值的金融快照

- `acc_gl_journal_entry_annual_summary`
- `m_journal_entry_aggregation_summary`
- `m_journal_entry_aggregation_tracking`
- `m_loan_arrears_aging`
- `m_loan_buy_down_fee_balance`
- `m_loan_capitalized_income_balance`
- `m_trial_balance`
- `m_wc_loan_balance`

建议至少将试算平衡、贷款逾期、营运资金贷款余额、买断费/资本化收益余额纳入正式
DWD/DWS；`m_journal_entry_aggregation_tracking` 可确认成 operational run fact。将全部留在
ODS 会显著削弱“金融语义冷启动”难度和真实性。

### M3. `m_wc_loan_payment_allocation_rule` 被误判成事实

该表列为 `wc_loan_id`, `transaction_type`, `allocation_types` 及审计字段，本质是贷款级分配规则，
不是业务事件或可加事实。当前 `event_or_relation + standalone_fact ->
dwd_wc_payment_allocation_rule` 为确定性错误。建议改为 `master_or_reference + rule_reference`，
或作为账户规则桥表；不应进入事实指标评分。

### M4. 三张直接下游表的语义形态需纠正

- `m_client_identifier`：证件卫星/客户属性关系，不是交易事实；应为 restricted satellite/bridge。
- `m_creditreport`：`national_id + credit_reports` 原始正文不应原样复制成 DWD；应保留受控 ODS，
  DWD 仅放报告批次、征信机构、时间、结果摘要或解析后的允许字段。
- `m_wc_loan_account_locks`：当前锁状态和 stacktrace 是 COB 技术运行状态，不是贷款业务事实；
  应为 operational_only，除非另建带采集时间的运行快照。

### M5. 确定性数据域误判

下列是由 `client/group/share/risk` 等关键词触发的高确定性误分：

| 当前表 | 当前域 | 建议域/板块 |
|---|---|---|
| `oauth_client_details` | CUST/CLNT | OPER/OTHR |
| `m_tax_group`, `m_tax_group_mappings` | CUST/CLNT | PROD/OTHR |
| `glim_accounts` | OTHR/OTHR | LOAN/LOAN |
| `gsim_accounts` | OTHR/OTHR | DPST/DPST |
| `m_account_transfer_standing_instructions`, `_history` | DPST/DPST | PAYM/PAYM |
| `m_tellers`, `m_cashiers` | OTHR 或 PAYM | PAYM/PAYM（机构维可辅属 ORGN） |
| `m_share_account_charge`, `_paid_by` | PROD/OTHR | INVS/ASTM |
| `m_share_product`, `_charge`, `_dividend_pay_out`, `_market_price` | PROD/OTHR | INVS/ASTM，产品定价可作辅域 PROD |
| `m_external_event`, `m_external_event_configuration` | RISK/OTHR | OPER/OTHR |
| `m_hook*` 五表 | RISK/OTHR | OPER/OTHR 或 CHNL/CHNL |
| `notification_generator`, `notification_mapper`, `sms_campaign`, `sms_messages_outbound` | RISK/OTHR | CHNL/CHNL |
| `m_survey*`, `ppi_*` | OTHR/OTHR | CUST/CLNT 或 CHNL/CHNL |

征信、逾期、拨备当前多归 LOAN。此项不是确定性错误，但 taxonomy 已明确 RISK 包含征信、
逾期、拨备，gold_v1 必须统一采用“业务归属 LOAN、风险主题 RISK”的主辅域策略，避免同一
语义在答案中漂移。

## Minor

1. `source_kind` 仅有 `master_or_reference/event_or_relation/technical` 三类，无法区分账户实体、
   规则、桥、周期快照、累积快照。建议 source_kind 扩为 entity/master/rule/event/bridge/snapshot/technical；
   disposition 保留“是否独立下游”的决策。
2. `grain: id` 过于机械。`m_trial_balance` 无 PK，实际候选粒度是 office + account + entry_date；
   关系表和历史表也需要业务复合粒度，而非仅使用 surrogate id。
3. `candidate` 不应出现在发布版 gold 中。需要改成 `human_reviewed_downstream`、
   `human_reviewed_component`、`human_reviewed_ods_only` 或 `security_reviewed` 等确定状态。

## 277 张表全覆盖规则与结果

本轮不是抽样。以下八个互斥 disposition 分区合计 277，复核规则和例外已经覆盖每张表：

| 当前 disposition | 数量 | 统一复核规则 | 例外/动作 |
|---|---:|---|---|
| standalone_dimension | 34 | 校验实体稳定性、是否含时变度量 | 四类账户主表需拆维度/快照；域错误按 M5 修正 |
| standalone_fact | 55 | 校验是否有业务事件/周期、金额和关联粒度 | wc 分配规则、账户锁、客户证件、信用报告按 M3/M4 修正 |
| bridge_source | 22 | 校验两端 FK 和关系有效期；允许不独立成表 | 已生成 7、candidate 15；gold 必须明确 consolidated target 或确认 ODS-only |
| snapshot_source | 8 | 校验快照日期和复合粒度 | 全部需按 M2 做正式决定，不能继续 candidate |
| rule_reference | 17 | 规则不作为可加事实；作为维度属性/桥输入 | 征信配置含 secret；wc 分配规则应加入本组 |
| component_source | 100 | 必须声明被哪个目标 join/enrich，否则不能叫 component | 当前 100 张均无实际下游引用；高价值余额/账户/参与方表优先补 target |
| operational_only | 25 | 默认 ODS-only，不参与银行指标 | 配置 value/JSON 按 B2 提升敏感等级 |
| security_excluded | 16 | 禁止通用下游，限定审计用途 | 8 张 candidate 状态按 B1 收敛 |

全覆盖后的人工决策原则：

- 40 张 technical 且只服务调度、权限、报表定义、hook/config 的表，允许确认成
  `human_reviewed_ods_only` 或 `security_reviewed`；它们不是遗漏事实。
- 规则、产品子配置和码值子表可以不独立生成 DWD，但必须在 gold 中给出
  `recommended_join_target`，否则无法判断模型提出的合并建议是否正确。
- 所有事件、关系、快照表逐项检查 PK/FK 后再决定独立事实；不能以表名含
  `history/transaction/mapping` 作为唯一依据。
- 所有含自由文本、JSON、generic value、account/document/contact 字段的表执行列级安全复核。

## 发布 gold_v1 前的最小修正清单

1. 修复 B1 的 8 张状态冲突，并对 B2 的 17 张补敏感等级和列级动作。
2. 将四类账户源表改成一源多目标的“稳定 DIM + 每日快照”。
3. 正式映射八张 snapshot_source；至少覆盖试算平衡、逾期、贷款余额。
4. 修正 wc 分配规则、账户锁、客户证件、信用报告四类错误。
5. 修正 M5 高确定性域误判；征信/逾期/拨备采用主辅域规范。
6. 为 100 张 component_source 和 15 张 candidate bridge 写入
   `recommended_join_target` 或确认 `human_reviewed_ods_only`。
7. 消除全部 173 个 `candidate` 后再生成不可见 benchmark gold；保留当前版本作为 weak label，
   不作为最终评分答案。

## 审查判定

- 作为资产生成和血缘规模基线：**有条件通过**。
- 作为表级领域分类 weak-label 数据：**有条件通过**，需在说明中披露规则生成性质。
- 作为模型语义冷启动 benchmark 的人工 gold_v1：**不通过，完成上述最小修正后复审**。
