# `retail_banking` 生成资产第二轮独立审查

## 结论

当前资产的**文件闭包、schema identity、SQL 可解析性和血缘闭包已经达到“可生成骨架”水平**，但不应作为已经完成的银行数仓基线验收。Gate 0–2 中存在 5 个 blocker：上游 schema 编译并非最终 schema、96 张 DIM/DWD 全部是 ODS 改名复制、DWS/ADS 由字段名启发式机械生成且存在错误指标、拨备事实选错来源、安全/PII 分类会把 secret 和客户信息标成普通内部数据。

因此本轮结论为：

- **作为 inventory + Doris DDL/血缘压力测试骨架：可用。**
- **作为“完整 Fineract → DIM/DWD/DWS/ADS 映射”和可验证银行数仓：阻断。**
- 建议保留 277 张 ODS 和 schema identity 框架，暂停把 96/30/19 张下游资产标为 reviewed/业务完成，先修复下面的 blocker。

当前数量核对：277 ODS、34 DIM、62 DWD、30 DWS、19 ADS，共 422 张。映射中 277 个源表均有记录，但只有 96 个 `reviewed`，181 个仍为 `candidate` 且 `downstream_targets` 为空。

## 已通过的机械检查

以下结果是真实的正向进展，但不能替代语义验收：

1. 固定了 Fineract commit `45d8e24f82c9c42c46a6762b24e102ad2c723824`。
2. 当前 snapshot 的 277 个表与 mapping 的 277 个表集合一致。
3. ODS DDL/model/data 三套文件各 277 个；DIM/DWD/DWS 和 ADS 的 DDL/model/task 文件闭包一致。
4. 每张生成表和字段都有稳定 schema identity；父任务报告 schema identity 校验通过。
5. 父任务报告 38 个测试通过、145 个任务均可做血缘解析。
6. ODS 都有统一 `load_time`，可满足当前 execution 的日期发现硬编码。
7. 映射没有把 `candidate` 直接生成 DIM/DWD；这一层 fail-closed 机制是正确方向。

我所在子任务环境没有可用 `conda`，本地 `make test` 停在 `conda: command not found`；上面的测试通过信息采用父任务最终验证结果。本报告的 blocker 均由生成器、mapping 和已生成 SQL 的静态证据得出，不依赖测试环境。

## Blocker

### B1. Gate 0 失败：schema 编译器漏掉嵌套 changelog，也没有编译完整约束

> 后续修复状态：schema 编译代码和针对性测试已完成；现有 snapshot/ODS 尚未重生成。新编译器已能递归覆盖 savings nested changelog，并默认对未审核 raw SQL fail closed。需要先提交显式 override/解析决策，再统一重生成资产，B1 才算最终关闭。

`tools/build_assets.py:479-512` 用文件 glob 代替递归解析 Liquibase master/include，并假设文件名排序就是执行顺序。该 glob 只取 `.../parts/*.xml`，已确认漏掉 savings 模块的 `parts/parts/*.xml`。

可复现的字段缺失：

- 上游 `fineract-savings/.../parts/parts/2003_add_accrued_till_date_to_savings_account.xml` 给 `m_savings_account` 增加 `accrued_till_date`，snapshot/ODS 中没有。
- 上游 `.../2005_add_external_id_to_savings_transaction.xml` 给 `m_savings_account_transaction` 增加 `external_id` 和唯一约束，snapshot/ODS 中没有。

同时 `parse_fineract_schema()` 只处理 create/add/drop/rename/modify 和 raw SQL warning（`build_assets.py:652-679`），没有应用：

- `addPrimaryKey`、`addUniqueConstraint`、`addForeignKeyConstraint`。
- `addNotNullConstraint` / `dropNotNullConstraint`。
- 默认值、序列以及其他会影响最终 schema 的 operation。

当前 snapshot 有 20 张表、24 个 raw SQL warning，但生成仍继续；6 张表没有解析出的 PK。Fineract changelog 中仅 PK/UK/FK/not-null 类 operation 就有数百个，mapping 因而无法声称 FK、业务键和最终 nullable 已被验证。

影响：277 可能是合理的 clean-install 表数量，但**字段级 schema 不是该 commit 的最终 schema**；所有下游和 seed data 都继承了错误字段集合。

必须修复：

1. 从实际 clean-install master 开始递归解析 `include/includeAll`，严格保持 master 顺序和 precondition/dbms。
2. 支持上述约束 operation；至少把 PK/UK/FK/nullable/default 写入 snapshot。
3. raw SQL 不能只记录 warning 后继续。受影响表必须人工 override 或使 Gate 0 fail closed。
4. 加回归测试，至少断言两个 savings 新字段存在，并将编译 schema 与真实 PostgreSQL clean install 的 `information_schema` 做 diff。

### B2. Gate 2 失败：96/96 张 DIM/DWD 都是 ODS 的一对一改名复制

`generate_reviewed_mid()` 对每个 reviewed source 复制源列；`_copy_task()`（`generate_assets.py:391-407`）执行 `TRUNCATE + SELECT 全部源列`。当前 34 DIM 和 62 DWD 无一例外。

这导致：

- `dim_customer`、`dim_loan_account` 等只是 `m_client`/`m_loan` 改名，没有一致性键、标准状态、维度代理键、有效期或当前标识。
- mapping 宣称 DIM 使用 `scd2_full_diff`，实际 model 全部 `materialized: full + replace_all`，DDL 也没有 `effective_from/effective_to/is_current`。策略声明与实现相反。
- mapping 宣称 DWD 使用 `incremental_restate`，实际 145 个 MID/ADS task 全部包含 `TRUNCATE TABLE`，无 `@etl_date`、无增量水位、无近期分区重述。
- `component_source`、规则表和 bridge 没有被 join/enrich 到 reviewed target；所谓 DWD 没有统一枚举、币种、冲正关系和业务语义。
- DAG 看起来是 ODS→DWD→DWS→ADS 四层，但 DIM/DWD 间没有真实业务依赖和整合，复杂度主要来自文件数量。

并非所有一对一 DWD 都不合理：不可变交易事件可以保留源粒度。但至少要完成字段标准化、冲正语义、业务日期、FK/维度关联和质量规则；维度必须真正实现选定的 SCD 策略。

必须修复：

1. 将 reviewed 定义从“列入硬编码集合”改为“有批准的 target column mapping + grain + business date + key + join/filter/reversal 规则”。
2. 先手工实现贷款、存款、GL 三个闭环，不要对全部 96 表继续用通用 copy renderer。
3. DIM 的 SCD2 声明和 SQL必须一致；若首版决定 SCD1/full，mapping 应如实标记，不能写 `scd2_full_diff`。
4. DWD 事件至少实现 `@etl_date`/水位、幂等重述、冲正保留与业务类型标准化。

### B3. Gate 2 失败：30 张 DWS 和 19 张 ADS 是启发式凑数，部分指标业务上错误

DWS 生成器不是由已审核 spec 驱动，而是：

- 固定优先表列表后任取前 30 个（`_summary_specs(..., limit=30)`，`generate_assets.py:552-582`）。
- 从字段名优先级猜日期，最多取 3 个固定名称的 group column。
- 看到名称含 amount/balance/principal/interest 等的前 4 个 DECIMAL 就直接 `SUM`（`generate_assets.py:534-549, 630-660`）。

可确认的错误包括：

1. `dws_loan_installment_daily` 使用 `created_date`，因为源真实字段是 `duedate` 而规则只识别 `due_date`；还款表现应主要按应还日/业务快照日。
2. `dws_cashier_transaction_daily` 使用 `created_date`，而源已有真正交易日 `txn_date`。
3. `dws_deposit_transaction_daily` 对 `running_balance_derived` 和 `cumulative_balance_derived` 做 SUM；运行余额是半可加/不可加指标，逐交易求和没有业务意义。
4. `dws_gl_journal_entry_daily` 对 office/organization running balance 求和，同时没有按 `type_enum` 分借贷；不能形成试算平衡。
5. `dws_loan_charge_daily` 将 `charge_amount_or_percentage` 直接求和，混合定额和百分比计费类型。
6. 贷款/存款/股份 transaction 汇总没有处理 reversed 状态，金额和笔数会把冲正记录直接累计。
7. `dws_office_cash_transfer_daily` 只保留 currency，丢掉 from/to office；下游不可能完成分支现金对账。
8. `dws_wc_loan_transaction_daily`、`dws_wc_loan_disbursement_daily` 没有 `wc_loan_id`/office/product/currency，退化成全组合计数/金额。
9. 30 张 DWS 中 13 张只有 `record_count`，没有可解释业务指标；其中 customer identifier、staff/officer assignment、external event 等并不是应机械生成的日汇总主题。

ADS 更严重：`generate_ads()` 明确称为 `Application projection`，19 张任务全部原样复制对应 DWS，未新增字段、过滤或计算。以下名称会误导消费者：

- `ads_trial_balance_daily` 只是 GL DWS 的复制，没有借贷拆分和平衡。
- `ads_provision_reconciliation_daily` 只有 provisioning history 记录数，没有拨备金额或差额。
- `ads_delinquency_migration_daily` 只有标签新增记录，没有 from/to bucket migration。
- `ads_branch_cash_reconciliation_daily` 没有分支维度和对账差额。
- `ads_collection_workbench_daily` 是按日计数，不是当前催收工作清单。

必须修复：

1. 删除 `limit=30` 和字段名自动 SUM；DWS 必须由逐表 `SummarySpec` override 驱动，并声明可加性、币种、reversal、业务日期和 grain。
2. 实现少而正确的核心 DWS：贷款每日快照、还款计划表现、贷款现金流、存款每日余额/流量、GL 日余额、机构现金、资产质量和拨备。
3. ADS 若只是同形复制，应删除；只有存在明确消费合同和应用计算时才生成。
4. 为上述 9 类错误增加结果级测试，而不是只测试 SQL 能解析。

### B4. 拨备事实使用错误源表，导致 ADS 名称与内容完全不符

mapping 将 `m_provisioning_history` 映射为 `dwd_loan_provision_snapshot`。该源表只有 run header 字段：`id`、`journal_entry_created`、创建/修改人员和日期，没有贷款、产品、机构、币种或拨备金额。

真正带拨备明细的是 `m_loanproduct_provisioning_entry`，包含 `history_id`、`criteria_id`、`currency_code`、`office_id`、`product_id`、`category_id`、`overdue_in_days`、`reseve_amount`、liability/expense account。它当前只是 candidate/snapshot source，完全没有下游 target。

结果是：

```text
m_provisioning_history
  → dwd_loan_provision_snapshot（实际只是 run header）
  → dws_loan_provision_snapshot_daily（只有 record_count）
  → ads_provision_reconciliation_daily（仍只有 record_count）
```

必须修复：将 history 作为 run header/批次维度，将 provisioning entry 作为拨备明细事实，join category/criteria/GL account，ADS 比较拨备明细金额与会计分录金额并输出差额。

### B5. Gate 1/2 安全门失败：table-name 敏感度规则漏掉 secret 和大量 PII

`_sensitivity()` 只匹配少数表名（`build_assets.py:761-777`），而不是扫描列语义。机械扫描发现至少 34 张被标为 `internal` 的表含明显 PII/identifier/secret 类列。

两个必须立即修正的 secret 表：

- `m_creditbureau_token` 含 `username`, `token`, `token_type`，当前为 `internal + component_source`，不是 `security_excluded/restricted`。
- `request_audit_table` 含 `authentication_token`, `password`, `email`, `mobile_number`, `username`, `ip_address`，当前为 `internal + operational_only`。

其他明显误标：

- `m_client` 含姓名、手机号、邮箱、账号、external id，却标 `internal`，生成的 `dim_customer` 也继承该标签。
- `m_staff` 含姓名、手机号、邮箱。
- `m_guarantor` 含姓名、地址、家庭/手机号码。
- `m_adhoc`、scheduled email/SMS outbound 含收件邮箱或手机号。
- `m_external_event.data` 是 BYTEA payload，当前被当 STRING 原样进入 `dwd_external_event`，既可能不可转换，也可能含敏感业务载荷。

必须修复：

1. 敏感度从列级规则推导，table override 优先；password/token/secret/connection 永远 security excluded。
2. ODS 如必须保留受限字段，model 标为 restricted 并只允许受限访问；DIM/DWD 默认删除、哈希或掩码。
3. external event 仅保留 envelope 元数据，二进制 payload 不进入普通分析层。
4. 添加测试：非受限 DIM/DWD/ADS 中 secret 列数量必须为 0。

## Major

### M1. 映射清单仍是候选清单，不是完整的 DIM/DWD/DWS/ADS 映射

- 277 条中 181 条（65.3%）是 `candidate`，且全部 `downstream_targets: []`。
- 254/277 条 grain 只是 `id`，没有业务粒度描述。
- 181 条 candidate 共用同一句泛化 rationale；62 facts、34 dimensions 也分别共用一句理由。
- mapping 没有 business date、source/business key、FK、target column mapping、join/filter/reversal、PII column policy。
- DWS/ADS 没有出现在逐源表 downstream target mapping 中；只能从生成代码间接推测。

建议将 current mapping 命名为 `fineract_table_inventory` 或把 `confidence` 全部真实地保留为 candidate；只有完成上述字段和评审的条目才升级 reviewed。

### M2. 多处领域/处置误分

建议至少修正：

| 表 | 当前 | 建议 |
|---|---|---|
| `m_external_event` | RISK + business fact | OPER/Integration + operational event |
| `m_business_date` | OTHR component | ORGN/REFR business-calendar rule |
| `m_batch_business_steps` | OTHR component | OPER rule/config |
| `m_password_validation_policy` | OTHR component | OPER security rule |
| `m_trial_balance` | OTHR snapshot | FINA reconciliation input |
| `m_tellers` | OTHR dimension | ORGN/PAYM teller dimension |
| `m_working_days` | OTHR dimension | ORGN/REFR calendar rule |
| `mix_taxonomy*`, `mix_xbrl_namespace` | OTHR | REFR/FINA reporting metadata |
| `ppi_*`, `m_survey_*` | OTHR | CHNL/RISK survey/scoring |
| `glim_accounts`, `gsim_accounts` | OTHR component | LOAN/DPST + group-account bridge |
| `m_interest_incentives` | OTHR component | PROD/DPST rate rule |
| `m_wc_loan_payment_allocation_rule` | standalone fact | WCLN rule reference/loan-level rule bridge |

`m_account_transfer_details` 是 transfer header/参与账户关系，没有金额；当前命名为 standalone fact 容易与 `m_account_transfer_transaction` 重复计数。应明确 header 和 transaction line 粒度。

### M3. Seed data 只满足“能 INSERT”，不满足 Fineract 状态机和对账

`generate_ods_data.py` 对所有 FK 默认填 1、所有 status 填 300、所有 amount/balance/principal/interest/fee/penalty 填 100（行 90–114）。这会制造明显不可能的业务数据。

例如 `m_loan_transaction` 的一条记录同时：amount=100、principal=100、interest=100、fee=100、penalty=100，组成合计 400；`is_reversed=FALSE` 但 reversal external id/reversed date 仍被填写。所有日期列也被赋同一天，无法形成合理申请→审批→放款→到期→还款状态序列。

GL smoke data恰好有一借一贷，但只验证字符串出现次数；尚未验证 type enum 的真实含义、科目类型、子账映射和金额勾稽。

建议把通用 generator 降级为 schema smoke fixture，并另建场景造数：客户/机构/产品→贷款申请/放款/计划/还款/冲正→GL；存款开户/存取/费用/利息→GL；逾期迁移→拨备。Gate 4 前不得称“referentially and accounting aligned”。

### M4. 质量规则只写在 YAML，没有执行资产

mapping 中列出了 `journal_debit_credit_balance`、loan/deposit reconciliation 等名称，但当前测试主要验证集合、标记、解析和少量 smoke 字符串，没有可运行的行级/金额级质量 SQL。需要把每条硬规则实现为测试查询或验证脚本，并让失败阻断生成/CI。

### M5. 全量 TRUNCATE 与项目默认日 slice 语义冲突

warehouse 默认 slice 为 `stat_date/D`，但所有生成 model 都声明 full/replace_all，所有 task TRUNCATE。当前可执行但无法演示项目最重要的增量重放、shadow-run partition 和 DAG 重构验证能力，也不适合 422 张大仓的运行成本。至少核心事件/DWS 应实现按日幂等删除插入或 Doris 分区覆盖。

## Minor

1. `ADS_NAMES` 包含若干没有对应 DWS 的名字，最终只生成 19/22，配置与产物容易漂移；manifest 应列出逐资产来源而不仅是 count。
2. DDL 将所有表统一 `DUPLICATE KEY`、`BUCKETS 1`，适合小型 smoke，不适合声称复杂/大规模；至少为维度、事件和大交易表分开 key/distribution 策略。
3. PostgreSQL `TIMESTAMP WITH TIME ZONE` 转 Doris `DATETIME` 时没有明确 UTC 规范；应在 mapping 记录 timezone normalization。
4. `_doris_type()` 对 BYTEA/JSON/数组等默认 STRING，需要显式编码/序列化规则，尤其 external-event payload。
5. model 的 primary entity code 由目标表全名机械生成（如 `DWD_LOAN_TRANSACTION`），不利于跨表复用一致实体；应使用 `LOAN_TRANSACTION`, `LOAN`, `CUSTOMER`, `OFFICE` 等语义实体并声明 foreign entities。

## 建议修复顺序

### 第一批：解除 blocker

1. 重写 changelog include 编译并重新生成 snapshot/ODS；对真实 PostgreSQL clean-install 做 schema diff。
2. 修正 secret/PII、拨备来源和上述领域误分；将未真正审核的条目降回 candidate。
3. 停止自动生成 DWS/ADS；先保留 ODS + 经过真实 SQL 设计的少量 DIM/DWD。
4. 手工完成三条纵向闭环：
   - 贷款：client/product/loan/schedule/transaction/charge/delinquency。
   - 存款：account/transaction/charge/interest/hold。
   - 会计：GL account/product mapping/journal/trial balance/subledger reconciliation。

### 第二批：语义和数据验收

1. 为每个 reviewed target 写独立 spec，生成器只负责渲染，不负责猜业务日期和 SUM。
2. 建设可闭环的场景数据，执行借贷、子账、还款计划、存款余额和拨备对账。
3. 实现日分区增量/重述，验证多日重跑和 shadow compare。
4. ADS 由真实消费问题驱动；同形投影一律删除。

## 最终判定

| Gate | 结果 | 说明 |
|---|---|---|
| Gate 0 来源固定与最终 schema | **FAIL / BLOCKER** | commit 固定，但漏 nested include、约束和 raw SQL override |
| Gate 1 映射完整与受审 | **FAIL / BLOCKER** | 181 candidate、目标映射不完整、领域/敏感度误分 |
| Gate 2 模型合理与非机械膨胀 | **FAIL / BLOCKER** | 96 张直接复制、30 张启发式汇总、19 张 ADS 原样投影 |
| 文件/identity/lineage 机械闭包 | **PASS** | 可作为大规模生成和血缘压力测试骨架 |

当前没有理由否定 Fineract 作为 ODS 底座；需要否定的是“已生成的 145 张下游表已经构成完成的银行数仓”这一结论。修复上述 blocker 后，277 ODS 仍可复用，但 DIM/DWD/DWS/ADS 应按业务闭环重做，而不是继续扩大机械生成数量。
