# Fineract 表到零售银行数仓映射清单

- 上游仓库：`https://github.com/apache/fineract`
- 固定 commit：`45d8e24f82c9c42c46a6762b24e102ad2c723824`
- 活动源表：277
- 建设下游的源表：100
- 口径：标准 Fineract PostgreSQL clean-install tenant changelog；不包含 tenant-store、custom 示例和历史 upgrade-only changelog。

## 领域统计

| 数据域 | 表数 |
|---|---:|
| CHNL 渠道与客户服务 | 21 |
| CUST 客户与参与方 | 15 |
| DPST 存款与储蓄 | 19 |
| FINA 总账与财务 | 12 |
| INVS 投资、份额与资产持有 | 12 |
| LOAN 贷款与信贷 | 76 |
| OPER 平台运营与安全 | 26 |
| ORGN 机构与员工 | 7 |
| OTHR 其它银行运营 | 19 |
| PAYM 支付结算 | 12 |
| PROD 产品、定价与税费 | 13 |
| REFR 公共参考与元数据 | 18 |
| RISK 风险、合规与审计 | 1 |
| WCLN 营运资金贷款 | 26 |

## 目标层统计

| 目标层 | 源表数 |
|---|---:|
| DIM | 36 |
| DWD | 64 |
| NONE | 177 |

## 完整映射

| Fineract 表 | ODS | 业务域 | disposition | 置信度 | 目标层 | 第一目标表 | 粒度 |
|---|---|---|---|---|---|---|---|
| acc_accounting_rule | ods_fineract_acc_accounting_rule | FINA 总账与财务 | standalone_dimension | human_reviewed | DIM | dim_accounting_rule | id |
| acc_gl_account | ods_fineract_acc_gl_account | FINA 总账与财务 | standalone_dimension | human_reviewed | DIM | dim_gl_account | id |
| acc_gl_closure | ods_fineract_acc_gl_closure | FINA 总账与财务 | standalone_fact | human_reviewed | DWD | dwd_gl_close_event | id |
| acc_gl_financial_activity_account | ods_fineract_acc_gl_financial_activity_account | FINA 总账与财务 | component_source | candidate | NONE | — | id |
| acc_gl_journal_entry | ods_fineract_acc_gl_journal_entry | FINA 总账与财务 | standalone_fact | human_reviewed | DWD | dwd_gl_journal_entry | id |
| acc_gl_journal_entry_annual_summary | ods_fineract_acc_gl_journal_entry_annual_summary | FINA 总账与财务 | snapshot_source | human_reviewed | DWD | dwd_gl_annual_balance_snapshot | gl_code, product_id, office_id, currency_code, owner_external_id, manual_entry, year_end_date |
| acc_product_mapping | ods_fineract_acc_product_mapping | FINA 总账与财务 | standalone_dimension | human_reviewed | DIM | bridge_product_gl_mapping | id |
| acc_rule_tags | ods_fineract_acc_rule_tags | FINA 总账与财务 | rule_reference | candidate | NONE | — | id |
| batch_custom_job_parameters | ods_fineract_batch_custom_job_parameters | OPER 平台运营与安全 | security_excluded | security_reviewed | NONE | — | id |
| c_account_number_format | ods_fineract_c_account_number_format | REFR 公共参考与元数据 | component_source | candidate | NONE | — | id |
| c_cache | ods_fineract_c_cache | OPER 平台运营与安全 | operational_only | candidate | NONE | — | id |
| c_configuration | ods_fineract_c_configuration | REFR 公共参考与元数据 | operational_only | candidate | NONE | — | id |
| c_external_service | ods_fineract_c_external_service | OTHR 其它银行运营 | operational_only | candidate | NONE | — | id |
| c_external_service_properties | ods_fineract_c_external_service_properties | OTHR 其它银行运营 | security_excluded | security_reviewed | NONE | — | source row |
| glim_accounts | ods_fineract_glim_accounts | LOAN 贷款与信贷 | component_source | candidate | NONE | — | id |
| gsim_accounts | ods_fineract_gsim_accounts | DPST 存款与储蓄 | component_source | candidate | NONE | — | id |
| interop_identifier | ods_fineract_interop_identifier | PAYM 支付结算 | component_source | candidate | NONE | — | id |
| job | ods_fineract_job | OPER 平台运营与安全 | security_excluded | security_reviewed | NONE | — | id |
| job_parameters | ods_fineract_job_parameters | OPER 平台运营与安全 | security_excluded | security_reviewed | NONE | — | id |
| job_run_history | ods_fineract_job_run_history | OPER 平台运营与安全 | operational_only | candidate | NONE | — | id |
| m_account_transfer_details | ods_fineract_m_account_transfer_details | PAYM 支付结算 | bridge_source | human_reviewed | DWD | dwd_account_transfer_instruction | id |
| m_account_transfer_standing_instructions | ods_fineract_m_account_transfer_standing_instructions | PAYM 支付结算 | component_source | candidate | NONE | — | id |
| m_account_transfer_standing_instructions_history | ods_fineract_m_account_transfer_standing_instructions_history | PAYM 支付结算 | standalone_fact | human_reviewed | DWD | dwd_standing_instruction_event | id |
| m_account_transfer_transaction | ods_fineract_m_account_transfer_transaction | PAYM 支付结算 | standalone_fact | human_reviewed | DWD | dwd_account_transfer_transaction | id |
| m_address | ods_fineract_m_address | CUST 客户与参与方 | standalone_dimension | human_reviewed | DIM | dim_address | id |
| m_adhoc | ods_fineract_m_adhoc | OTHR 其它银行运营 | security_excluded | security_reviewed | NONE | — | id |
| m_appuser | ods_fineract_m_appuser | OPER 平台运营与安全 | security_excluded | security_reviewed | NONE | — | id |
| m_appuser_previous_password | ods_fineract_m_appuser_previous_password | OPER 平台运营与安全 | security_excluded | security_reviewed | NONE | — | id |
| m_appuser_role | ods_fineract_m_appuser_role | OPER 平台运营与安全 | security_excluded | security_reviewed | NONE | — | appuser_id, role_id |
| m_batch_business_steps | ods_fineract_m_batch_business_steps | OTHR 其它银行运营 | component_source | candidate | NONE | — | id |
| m_business_date | ods_fineract_m_business_date | OPER 平台运营与安全 | component_source | candidate | NONE | — | id |
| m_calendar | ods_fineract_m_calendar | CHNL 渠道与客户服务 | standalone_dimension | human_reviewed | DIM | dim_meeting_calendar | id |
| m_calendar_history | ods_fineract_m_calendar_history | CHNL 渠道与客户服务 | component_source | candidate | NONE | — | id |
| m_calendar_instance | ods_fineract_m_calendar_instance | CHNL 渠道与客户服务 | component_source | candidate | NONE | — | id |
| m_cashier_transactions | ods_fineract_m_cashier_transactions | PAYM 支付结算 | standalone_fact | human_reviewed | DWD | dwd_cashier_transaction | id |
| m_cashiers | ods_fineract_m_cashiers | PAYM 支付结算 | component_source | candidate | NONE | — | id |
| m_charge | ods_fineract_m_charge | PROD 产品、定价与税费 | standalone_dimension | human_reviewed | DIM | dim_charge_definition | id |
| m_client | ods_fineract_m_client | CUST 客户与参与方 | standalone_dimension | human_reviewed | DIM | dim_customer | id |
| m_client_address | ods_fineract_m_client_address | CUST 客户与参与方 | bridge_source | human_reviewed | DWD | bridge_customer_address | id |
| m_client_attendance | ods_fineract_m_client_attendance | CUST 客户与参与方 | standalone_fact | human_reviewed | DWD | dwd_group_meeting_attendance | id |
| m_client_charge | ods_fineract_m_client_charge | CUST 客户与参与方 | snapshot_source | human_reviewed | DWD | dwd_client_charge | id |
| m_client_charge_paid_by | ods_fineract_m_client_charge_paid_by | CUST 客户与参与方 | standalone_fact | human_reviewed | DWD | dwd_client_charge_allocation | client_charge_id, client_transaction_id, id |
| m_client_collateral_management | ods_fineract_m_client_collateral_management | LOAN 贷款与信贷 | component_source | candidate | NONE | — | id |
| m_client_identifier | ods_fineract_m_client_identifier | CUST 客户与参与方 | bridge_source | candidate | NONE | — | id |
| m_client_non_person | ods_fineract_m_client_non_person | CUST 客户与参与方 | component_source | candidate | NONE | — | id |
| m_client_transaction | ods_fineract_m_client_transaction | CUST 客户与参与方 | standalone_fact | human_reviewed | DWD | dwd_client_transaction | id |
| m_client_transfer_details | ods_fineract_m_client_transfer_details | CUST 客户与参与方 | snapshot_source | human_reviewed | DWD | dwd_customer_transfer_event | id |
| m_code | ods_fineract_m_code | REFR 公共参考与元数据 | component_source | candidate | NONE | — | id |
| m_code_value | ods_fineract_m_code_value | REFR 公共参考与元数据 | standalone_dimension | human_reviewed | DIM | dim_code_value | code_id, id |
| m_collateral_management | ods_fineract_m_collateral_management | LOAN 贷款与信贷 | standalone_dimension | human_reviewed | DIM | dim_collateral_type | id |
| m_command | ods_fineract_m_command | OPER 平台运营与安全 | security_excluded | security_reviewed | NONE | — | id |
| m_creditbureau | ods_fineract_m_creditbureau | LOAN 贷款与信贷 | standalone_dimension | human_reviewed | DIM | dim_credit_bureau | id |
| m_creditbureau_configuration | ods_fineract_m_creditbureau_configuration | LOAN 贷款与信贷 | security_excluded | security_reviewed | NONE | — | id |
| m_creditbureau_loanproduct_mapping | ods_fineract_m_creditbureau_loanproduct_mapping | LOAN 贷款与信贷 | bridge_source | candidate | NONE | — | id |
| m_creditbureau_token | ods_fineract_m_creditbureau_token | LOAN 贷款与信贷 | security_excluded | security_reviewed | NONE | — | id |
| m_creditreport | ods_fineract_m_creditreport | LOAN 贷款与信贷 | security_excluded | security_reviewed | NONE | — | id |
| m_currency | ods_fineract_m_currency | PROD 产品、定价与税费 | standalone_dimension | human_reviewed | DIM | dim_currency | code |
| m_delinquency_bucket | ods_fineract_m_delinquency_bucket | LOAN 贷款与信贷 | standalone_dimension | human_reviewed | DIM | dim_delinquency_bucket | id |
| m_delinquency_bucket_mappings | ods_fineract_m_delinquency_bucket_mappings | LOAN 贷款与信贷 | bridge_source | candidate | NONE | — | id |
| m_delinquency_range | ods_fineract_m_delinquency_range | LOAN 贷款与信贷 | standalone_dimension | human_reviewed | DIM | dim_delinquency_range | id |
| m_deposit_account_on_hold_transaction | ods_fineract_m_deposit_account_on_hold_transaction | DPST 存款与储蓄 | standalone_fact | human_reviewed | DWD | dwd_deposit_hold_event | id |
| m_deposit_account_recurring_detail | ods_fineract_m_deposit_account_recurring_detail | DPST 存款与储蓄 | component_source | candidate | NONE | — | id |
| m_deposit_account_term_and_preclosure | ods_fineract_m_deposit_account_term_and_preclosure | DPST 存款与储蓄 | component_source | candidate | NONE | — | id |
| m_deposit_product_interest_rate_chart | ods_fineract_m_deposit_product_interest_rate_chart | DPST 存款与储蓄 | component_source | candidate | NONE | — | source row |
| m_deposit_product_recurring_detail | ods_fineract_m_deposit_product_recurring_detail | DPST 存款与储蓄 | component_source | candidate | NONE | — | id |
| m_deposit_product_term_and_preclosure | ods_fineract_m_deposit_product_term_and_preclosure | DPST 存款与储蓄 | component_source | candidate | NONE | — | id |
| m_document | ods_fineract_m_document | CHNL 渠道与客户服务 | component_source | candidate | NONE | — | id |
| m_entity_datatable_check | ods_fineract_m_entity_datatable_check | REFR 公共参考与元数据 | component_source | candidate | NONE | — | id |
| m_entity_relation | ods_fineract_m_entity_relation | REFR 公共参考与元数据 | bridge_source | candidate | NONE | — | id |
| m_entity_to_entity_access | ods_fineract_m_entity_to_entity_access | REFR 公共参考与元数据 | component_source | candidate | NONE | — | id |
| m_entity_to_entity_mapping | ods_fineract_m_entity_to_entity_mapping | REFR 公共参考与元数据 | bridge_source | candidate | NONE | — | id |
| m_external_asset_owner | ods_fineract_m_external_asset_owner | INVS 投资、份额与资产持有 | standalone_dimension | human_reviewed | DIM | dim_asset_owner | id |
| m_external_asset_owner_journal_entry_mapping | ods_fineract_m_external_asset_owner_journal_entry_mapping | FINA 总账与财务 | bridge_source | human_reviewed | DWD | bridge_asset_owner_gl_entry | id |
| m_external_asset_owner_loan_product_configurable_attributes | ods_fineract_m_external_asset_owner_loan_product_config_11bc4520 | LOAN 贷款与信贷 | component_source | candidate | NONE | — | id |
| m_external_asset_owner_transfer | ods_fineract_m_external_asset_owner_transfer | INVS 投资、份额与资产持有 | snapshot_source | human_reviewed | DWD | dwd_loan_ownership_transfer | id |
| m_external_asset_owner_transfer_details | ods_fineract_m_external_asset_owner_transfer_details | INVS 投资、份额与资产持有 | standalone_fact | human_reviewed | DWD | dwd_loan_ownership_transfer_detail | asset_owner_transfer_id, id |
| m_external_asset_owner_transfer_journal_entry_mapping | ods_fineract_m_external_asset_owner_transfer_journal_en_0adfde70 | FINA 总账与财务 | bridge_source | candidate | NONE | — | id |
| m_external_asset_owner_transfer_loan_mapping | ods_fineract_m_external_asset_owner_transfer_loan_mapping | LOAN 贷款与信贷 | bridge_source | candidate | NONE | — | id |
| m_external_event | ods_fineract_m_external_event | OPER 平台运营与安全 | security_excluded | security_reviewed | NONE | — | id |
| m_external_event_configuration | ods_fineract_m_external_event_configuration | OPER 平台运营与安全 | rule_reference | candidate | NONE | — | type |
| m_family_members | ods_fineract_m_family_members | CUST 客户与参与方 | component_source | candidate | NONE | — | id |
| m_field_configuration | ods_fineract_m_field_configuration | REFR 公共参考与元数据 | rule_reference | candidate | NONE | — | id |
| m_floating_rates | ods_fineract_m_floating_rates | PROD 产品、定价与税费 | standalone_dimension | human_reviewed | DIM | dim_rate_index | id |
| m_floating_rates_periods | ods_fineract_m_floating_rates_periods | PROD 产品、定价与税费 | component_source | candidate | NONE | — | id |
| m_fund | ods_fineract_m_fund | ORGN 机构与员工 | component_source | candidate | NONE | — | id |
| m_group | ods_fineract_m_group | CUST 客户与参与方 | standalone_dimension | human_reviewed | DIM | dim_customer_group | id |
| m_group_client | ods_fineract_m_group_client | CUST 客户与参与方 | bridge_source | human_reviewed | DWD | bridge_group_customer | group_id, client_id |
| m_group_level | ods_fineract_m_group_level | CUST 客户与参与方 | standalone_dimension | human_reviewed | DIM | dim_customer_group_level | id |
| m_group_roles | ods_fineract_m_group_roles | CUST 客户与参与方 | bridge_source | human_reviewed | DWD | bridge_group_customer_role | id |
| m_guarantor | ods_fineract_m_guarantor | LOAN 贷款与信贷 | bridge_source | human_reviewed | DWD | dwd_loan_guarantor_relation | id |
| m_guarantor_funding_details | ods_fineract_m_guarantor_funding_details | LOAN 贷款与信贷 | snapshot_source | human_reviewed | DWD | dwd_guarantee_commitment_snapshot | id |
| m_guarantor_transaction | ods_fineract_m_guarantor_transaction | LOAN 贷款与信贷 | bridge_source | human_reviewed | DWD | bridge_guarantee_transaction | id |
| m_holiday | ods_fineract_m_holiday | ORGN 机构与员工 | standalone_dimension | human_reviewed | DIM | dim_holiday | id |
| m_holiday_office | ods_fineract_m_holiday_office | ORGN 机构与员工 | bridge_source | human_reviewed | DWD | bridge_office_holiday | holiday_id, office_id |
| m_hook | ods_fineract_m_hook | OPER 平台运营与安全 | operational_only | candidate | NONE | — | id |
| m_hook_configuration | ods_fineract_m_hook_configuration | OPER 平台运营与安全 | security_excluded | security_reviewed | NONE | — | id |
| m_hook_registered_events | ods_fineract_m_hook_registered_events | OPER 平台运营与安全 | operational_only | candidate | NONE | — | id |
| m_hook_schema | ods_fineract_m_hook_schema | OPER 平台运营与安全 | operational_only | candidate | NONE | — | id |
| m_hook_templates | ods_fineract_m_hook_templates | OPER 平台运营与安全 | operational_only | candidate | NONE | — | id |
| m_image | ods_fineract_m_image | CHNL 渠道与客户服务 | component_source | candidate | NONE | — | id |
| m_import_document | ods_fineract_m_import_document | CHNL 渠道与客户服务 | component_source | candidate | NONE | — | id |
| m_interest_incentives | ods_fineract_m_interest_incentives | OTHR 其它银行运营 | component_source | candidate | NONE | — | id |
| m_interest_rate_chart | ods_fineract_m_interest_rate_chart | PROD 产品、定价与税费 | component_source | candidate | NONE | — | id |
| m_interest_rate_slab | ods_fineract_m_interest_rate_slab | PROD 产品、定价与税费 | component_source | candidate | NONE | — | id |
| m_journal_entry_aggregation_summary | ods_fineract_m_journal_entry_aggregation_summary | FINA 总账与财务 | snapshot_source | human_reviewed | DWD | dwd_gl_aggregation_summary | gl_account_id, product_id, office_id, entity_type_enum, external_owner_id, manual_entry, aggregated_on_date |
| m_journal_entry_aggregation_tracking | ods_fineract_m_journal_entry_aggregation_tracking | FINA 总账与财务 | standalone_fact | human_reviewed | DWD | dwd_gl_aggregation_run | id |
| m_loan | ods_fineract_m_loan | LOAN 贷款与信贷 | standalone_dimension | human_reviewed | DIM | dim_loan_account | id |
| m_loan_account_locks | ods_fineract_m_loan_account_locks | LOAN 贷款与信贷 | component_source | candidate | NONE | — | loan_id |
| m_loan_amortization_allocation_mapping | ods_fineract_m_loan_amortization_allocation_mapping | LOAN 贷款与信贷 | bridge_source | candidate | NONE | — | id |
| m_loan_approved_amount_history | ods_fineract_m_loan_approved_amount_history | LOAN 贷款与信贷 | standalone_fact | human_reviewed | DWD | dwd_loan_approval_event | id |
| m_loan_arrears_aging | ods_fineract_m_loan_arrears_aging | LOAN 贷款与信贷 | snapshot_source | human_reviewed | DWD | dwd_loan_arrears_snapshot | loan_id, snapshot_date |
| m_loan_buy_down_fee_balance | ods_fineract_m_loan_buy_down_fee_balance | LOAN 贷款与信贷 | snapshot_source | human_reviewed | DWD | dwd_loan_buy_down_fee_balance | id |
| m_loan_capitalized_income_balance | ods_fineract_m_loan_capitalized_income_balance | LOAN 贷款与信贷 | snapshot_source | human_reviewed | DWD | dwd_loan_capitalized_income_balance | id |
| m_loan_charge | ods_fineract_m_loan_charge | LOAN 贷款与信贷 | snapshot_source | human_reviewed | DWD | dwd_loan_charge | id |
| m_loan_charge_paid_by | ods_fineract_m_loan_charge_paid_by | LOAN 贷款与信贷 | standalone_fact | human_reviewed | DWD | dwd_loan_charge_allocation | loan_charge_id, loan_transaction_id, id |
| m_loan_charge_tax_details | ods_fineract_m_loan_charge_tax_details | LOAN 贷款与信贷 | component_source | candidate | NONE | — | id |
| m_loan_collateral | ods_fineract_m_loan_collateral | LOAN 贷款与信贷 | component_source | candidate | NONE | — | id |
| m_loan_collateral_management | ods_fineract_m_loan_collateral_management | LOAN 贷款与信贷 | standalone_fact | human_reviewed | DWD | dwd_loan_collateral_pledge | id |
| m_loan_credit_allocation_rule | ods_fineract_m_loan_credit_allocation_rule | LOAN 贷款与信贷 | rule_reference | candidate | NONE | — | id |
| m_loan_delinquency_action | ods_fineract_m_loan_delinquency_action | LOAN 贷款与信贷 | standalone_fact | human_reviewed | DWD | dwd_collection_action | id |
| m_loan_delinquency_tag_history | ods_fineract_m_loan_delinquency_tag_history | LOAN 贷款与信贷 | standalone_fact | human_reviewed | DWD | dwd_loan_delinquency_event | id |
| m_loan_disbursement_detail | ods_fineract_m_loan_disbursement_detail | LOAN 贷款与信贷 | standalone_fact | human_reviewed | DWD | dwd_loan_disbursement | id |
| m_loan_installment_charge | ods_fineract_m_loan_installment_charge | LOAN 贷款与信贷 | standalone_fact | human_reviewed | DWD | dwd_loan_installment_charge | loan_schedule_id, loan_charge_id, id |
| m_loan_installment_delinquency_tag | ods_fineract_m_loan_installment_delinquency_tag | LOAN 贷款与信贷 | component_source | candidate | NONE | — | id |
| m_loan_interest_recalculation_additional_details | ods_fineract_m_loan_interest_recalculation_additional_details | LOAN 贷款与信贷 | component_source | candidate | NONE | — | id |
| m_loan_officer_assignment_history | ods_fineract_m_loan_officer_assignment_history | LOAN 贷款与信贷 | standalone_fact | human_reviewed | DWD | dwd_loan_officer_assignment | id |
| m_loan_originator | ods_fineract_m_loan_originator | LOAN 贷款与信贷 | component_source | candidate | NONE | — | id |
| m_loan_originator_mapping | ods_fineract_m_loan_originator_mapping | LOAN 贷款与信贷 | bridge_source | candidate | NONE | — | id |
| m_loan_overdue_installment_charge | ods_fineract_m_loan_overdue_installment_charge | LOAN 贷款与信贷 | component_source | candidate | NONE | — | id |
| m_loan_payment_allocation_rule | ods_fineract_m_loan_payment_allocation_rule | LOAN 贷款与信贷 | rule_reference | candidate | NONE | — | id |
| m_loan_product_credit_allocation_rule | ods_fineract_m_loan_product_credit_allocation_rule | LOAN 贷款与信贷 | rule_reference | candidate | NONE | — | id |
| m_loan_product_payment_allocation_rule | ods_fineract_m_loan_product_payment_allocation_rule | LOAN 贷款与信贷 | rule_reference | candidate | NONE | — | id |
| m_loan_progressive_model | ods_fineract_m_loan_progressive_model | LOAN 贷款与信贷 | component_source | candidate | NONE | — | id |
| m_loan_rate | ods_fineract_m_loan_rate | LOAN 贷款与信贷 | standalone_dimension | human_reviewed | DIM | bridge_loan_rate | loan_id, rate_id |
| m_loan_reage_parameter | ods_fineract_m_loan_reage_parameter | LOAN 贷款与信贷 | component_source | candidate | NONE | — | id |
| m_loan_reamortization_parameter | ods_fineract_m_loan_reamortization_parameter | LOAN 贷款与信贷 | component_source | candidate | NONE | — | id |
| m_loan_recalculation_details | ods_fineract_m_loan_recalculation_details | LOAN 贷款与信贷 | standalone_dimension | human_reviewed | DIM | dim_loan_interest_terms_satellite | loan_id |
| m_loan_repayment_schedule | ods_fineract_m_loan_repayment_schedule | LOAN 贷款与信贷 | snapshot_source | human_reviewed | DWD | dwd_loan_installment | loan_id, installment, id |
| m_loan_repayment_schedule_history | ods_fineract_m_loan_repayment_schedule_history | LOAN 贷款与信贷 | snapshot_source | human_reviewed | DWD | dwd_loan_installment_version | loan_id, loan_reschedule_request_id, version, installment |
| m_loan_reschedule_request | ods_fineract_m_loan_reschedule_request | LOAN 贷款与信贷 | snapshot_source | human_reviewed | DWD | dwd_loan_restructure_event | id |
| m_loan_reschedule_request_term_variations_mapping | ods_fineract_m_loan_reschedule_request_term_variations_mapping | LOAN 贷款与信贷 | bridge_source | candidate | NONE | — | id |
| m_loan_status_change_history | ods_fineract_m_loan_status_change_history | LOAN 贷款与信贷 | standalone_fact | human_reviewed | DWD | dwd_loan_lifecycle_event | id |
| m_loan_term_variations | ods_fineract_m_loan_term_variations | LOAN 贷款与信贷 | component_source | candidate | NONE | — | id |
| m_loan_topup | ods_fineract_m_loan_topup | LOAN 贷款与信贷 | component_source | candidate | NONE | — | id |
| m_loan_tranche_charges | ods_fineract_m_loan_tranche_charges | LOAN 贷款与信贷 | component_source | candidate | NONE | — | id |
| m_loan_tranche_disbursement_charge | ods_fineract_m_loan_tranche_disbursement_charge | LOAN 贷款与信贷 | component_source | candidate | NONE | — | id |
| m_loan_transaction | ods_fineract_m_loan_transaction | LOAN 贷款与信贷 | standalone_fact | human_reviewed | DWD | dwd_loan_transaction | id |
| m_loan_transaction_relation | ods_fineract_m_loan_transaction_relation | LOAN 贷款与信贷 | bridge_source | human_reviewed | DWD | bridge_loan_transaction_relation | id |
| m_loan_transaction_repayment_schedule_mapping | ods_fineract_m_loan_transaction_repayment_schedule_mapping | LOAN 贷款与信贷 | standalone_fact | human_reviewed | DWD | dwd_loan_repayment_allocation | loan_transaction_id, loan_repayment_schedule_id, id |
| m_loanproduct_provisioning_entry | ods_fineract_m_loanproduct_provisioning_entry | LOAN 贷款与信贷 | snapshot_source | human_reviewed | DWD | dwd_loan_provision_entry | history_id, office_id, product_id, category_id, criteria_id, id |
| m_loanproduct_provisioning_mapping | ods_fineract_m_loanproduct_provisioning_mapping | LOAN 贷款与信贷 | bridge_source | candidate | NONE | — | id |
| m_mandatory_savings_schedule | ods_fineract_m_mandatory_savings_schedule | DPST 存款与储蓄 | component_source | candidate | NONE | — | id |
| m_meeting | ods_fineract_m_meeting | CHNL 渠道与客户服务 | component_source | candidate | NONE | — | id |
| m_note | ods_fineract_m_note | CHNL 渠道与客户服务 | component_source | candidate | NONE | — | id |
| m_office | ods_fineract_m_office | ORGN 机构与员工 | standalone_dimension | human_reviewed | DIM | dim_office | id |
| m_office_transaction | ods_fineract_m_office_transaction | PAYM 支付结算 | standalone_fact | human_reviewed | DWD | dwd_office_cash_transfer | id |
| m_organisation_creditbureau | ods_fineract_m_organisation_creditbureau | LOAN 贷款与信贷 | component_source | candidate | NONE | — | id |
| m_organisation_currency | ods_fineract_m_organisation_currency | PROD 产品、定价与税费 | component_source | candidate | NONE | — | id |
| m_password_validation_policy | ods_fineract_m_password_validation_policy | OTHR 其它银行运营 | component_source | candidate | NONE | — | id |
| m_payment_detail | ods_fineract_m_payment_detail | PAYM 支付结算 | component_source | candidate | NONE | — | id |
| m_payment_type | ods_fineract_m_payment_type | PAYM 支付结算 | standalone_dimension | human_reviewed | DIM | dim_payment_type | id |
| m_permission | ods_fineract_m_permission | OPER 平台运营与安全 | operational_only | candidate | NONE | — | id |
| m_portfolio_account_associations | ods_fineract_m_portfolio_account_associations | OTHR 其它银行运营 | component_source | candidate | NONE | — | id |
| m_portfolio_command_source | ods_fineract_m_portfolio_command_source | OPER 平台运营与安全 | security_excluded | security_reviewed | NONE | — | id |
| m_product_loan | ods_fineract_m_product_loan | LOAN 贷款与信贷 | standalone_dimension | human_reviewed | DIM | dim_loan_product | id |
| m_product_loan_charge | ods_fineract_m_product_loan_charge | LOAN 贷款与信贷 | component_source | candidate | NONE | — | product_loan_id, charge_id |
| m_product_loan_configurable_attributes | ods_fineract_m_product_loan_configurable_attributes | LOAN 贷款与信贷 | component_source | candidate | NONE | — | id |
| m_product_loan_floating_rates | ods_fineract_m_product_loan_floating_rates | LOAN 贷款与信贷 | component_source | candidate | NONE | — | id |
| m_product_loan_guarantee_details | ods_fineract_m_product_loan_guarantee_details | LOAN 贷款与信贷 | component_source | candidate | NONE | — | id |
| m_product_loan_rate | ods_fineract_m_product_loan_rate | LOAN 贷款与信贷 | component_source | candidate | NONE | — | product_loan_id, rate_id |
| m_product_loan_recalculation_details | ods_fineract_m_product_loan_recalculation_details | LOAN 贷款与信贷 | component_source | candidate | NONE | — | id |
| m_product_loan_variable_installment_config | ods_fineract_m_product_loan_variable_installment_config | LOAN 贷款与信贷 | component_source | candidate | NONE | — | id |
| m_product_loan_variations_borrower_cycle | ods_fineract_m_product_loan_variations_borrower_cycle | LOAN 贷款与信贷 | component_source | candidate | NONE | — | id |
| m_product_mix | ods_fineract_m_product_mix | PROD 产品、定价与税费 | component_source | candidate | NONE | — | id |
| m_provision_category | ods_fineract_m_provision_category | LOAN 贷款与信贷 | standalone_dimension | human_reviewed | DIM | dim_provision_category | id |
| m_provisioning_criteria | ods_fineract_m_provisioning_criteria | LOAN 贷款与信贷 | rule_reference | candidate | NONE | — | id |
| m_provisioning_criteria_definition | ods_fineract_m_provisioning_criteria_definition | LOAN 贷款与信贷 | rule_reference | candidate | NONE | — | id |
| m_provisioning_history | ods_fineract_m_provisioning_history | LOAN 贷款与信贷 | standalone_fact | human_reviewed | DWD | dwd_loan_provision_run | id |
| m_rate | ods_fineract_m_rate | PROD 产品、定价与税费 | standalone_dimension | human_reviewed | DIM | dim_rate | id |
| m_repayment_with_post_dated_checks | ods_fineract_m_repayment_with_post_dated_checks | PAYM 支付结算 | component_source | candidate | NONE | — | id |
| m_report_mailing_job | ods_fineract_m_report_mailing_job | REFR 公共参考与元数据 | security_excluded | security_reviewed | NONE | — | id |
| m_report_mailing_job_configuration | ods_fineract_m_report_mailing_job_configuration | REFR 公共参考与元数据 | security_excluded | security_reviewed | NONE | — | id |
| m_report_mailing_job_run_history | ods_fineract_m_report_mailing_job_run_history | REFR 公共参考与元数据 | operational_only | candidate | NONE | — | id |
| m_role | ods_fineract_m_role | OPER 平台运营与安全 | operational_only | candidate | NONE | — | id |
| m_role_permission | ods_fineract_m_role_permission | OPER 平台运营与安全 | operational_only | candidate | NONE | — | role_id, permission_id |
| m_savings_account | ods_fineract_m_savings_account | DPST 存款与储蓄 | standalone_dimension | human_reviewed | DIM | dim_deposit_account | id |
| m_savings_account_charge | ods_fineract_m_savings_account_charge | DPST 存款与储蓄 | snapshot_source | human_reviewed | DWD | dwd_deposit_charge | id |
| m_savings_account_charge_paid_by | ods_fineract_m_savings_account_charge_paid_by | DPST 存款与储蓄 | standalone_fact | human_reviewed | DWD | dwd_deposit_charge_allocation | savings_account_charge_id, savings_account_transaction_id, id |
| m_savings_account_interest_rate_chart | ods_fineract_m_savings_account_interest_rate_chart | DPST 存款与储蓄 | component_source | candidate | NONE | — | id |
| m_savings_account_interest_rate_slab | ods_fineract_m_savings_account_interest_rate_slab | DPST 存款与储蓄 | component_source | candidate | NONE | — | id |
| m_savings_account_transaction | ods_fineract_m_savings_account_transaction | DPST 存款与储蓄 | standalone_fact | human_reviewed | DWD | dwd_deposit_transaction | id |
| m_savings_account_transaction_tax_details | ods_fineract_m_savings_account_transaction_tax_details | DPST 存款与储蓄 | standalone_fact | human_reviewed | DWD | dwd_deposit_transaction_tax | savings_transaction_id, tax_component_id, id |
| m_savings_interest_incentives | ods_fineract_m_savings_interest_incentives | DPST 存款与储蓄 | component_source | candidate | NONE | — | id |
| m_savings_officer_assignment_history | ods_fineract_m_savings_officer_assignment_history | DPST 存款与储蓄 | standalone_fact | human_reviewed | DWD | dwd_deposit_officer_assignment | id |
| m_savings_product | ods_fineract_m_savings_product | DPST 存款与储蓄 | standalone_dimension | human_reviewed | DIM | dim_deposit_product | id |
| m_savings_product_charge | ods_fineract_m_savings_product_charge | DPST 存款与储蓄 | component_source | candidate | NONE | — | savings_product_id, charge_id |
| m_share_account | ods_fineract_m_share_account | INVS 投资、份额与资产持有 | standalone_dimension | human_reviewed | DIM | dim_share_account | id |
| m_share_account_charge | ods_fineract_m_share_account_charge | INVS 投资、份额与资产持有 | snapshot_source | human_reviewed | DWD | dwd_share_charge_snapshot | id |
| m_share_account_charge_paid_by | ods_fineract_m_share_account_charge_paid_by | INVS 投资、份额与资产持有 | standalone_fact | human_reviewed | DWD | dwd_share_charge_allocation | share_transaction_id, charge_transaction_id, id |
| m_share_account_dividend_details | ods_fineract_m_share_account_dividend_details | INVS 投资、份额与资产持有 | standalone_fact | human_reviewed | DWD | dwd_share_dividend | dividend_pay_out_id, account_id, id |
| m_share_account_transactions | ods_fineract_m_share_account_transactions | INVS 投资、份额与资产持有 | standalone_fact | human_reviewed | DWD | dwd_share_transaction | id |
| m_share_product | ods_fineract_m_share_product | INVS 投资、份额与资产持有 | standalone_dimension | human_reviewed | DIM | dim_share_product | id |
| m_share_product_charge | ods_fineract_m_share_product_charge | INVS 投资、份额与资产持有 | component_source | candidate | NONE | — | product_id, charge_id |
| m_share_product_dividend_pay_out | ods_fineract_m_share_product_dividend_pay_out | INVS 投资、份额与资产持有 | component_source | candidate | NONE | — | id |
| m_share_product_market_price | ods_fineract_m_share_product_market_price | INVS 投资、份额与资产持有 | snapshot_source | human_reviewed | DWD | dwd_share_market_price | product_id, from_date |
| m_staff | ods_fineract_m_staff | ORGN 机构与员工 | standalone_dimension | human_reviewed | DIM | dim_staff | id |
| m_staff_assignment_history | ods_fineract_m_staff_assignment_history | ORGN 机构与员工 | standalone_fact | human_reviewed | DWD | dwd_staff_assignment | id |
| m_survey_components | ods_fineract_m_survey_components | CHNL 渠道与客户服务 | component_source | candidate | NONE | — | id |
| m_survey_lookup_tables | ods_fineract_m_survey_lookup_tables | CHNL 渠道与客户服务 | component_source | candidate | NONE | — | id |
| m_survey_questions | ods_fineract_m_survey_questions | CHNL 渠道与客户服务 | component_source | candidate | NONE | — | id |
| m_survey_responses | ods_fineract_m_survey_responses | CHNL 渠道与客户服务 | component_source | candidate | NONE | — | id |
| m_survey_scorecards | ods_fineract_m_survey_scorecards | CHNL 渠道与客户服务 | standalone_fact | human_reviewed | DWD | dwd_survey_response | id |
| m_surveys | ods_fineract_m_surveys | CHNL 渠道与客户服务 | standalone_dimension | human_reviewed | DIM | dim_survey | id |
| m_tax_component | ods_fineract_m_tax_component | PROD 产品、定价与税费 | component_source | candidate | NONE | — | id |
| m_tax_component_history | ods_fineract_m_tax_component_history | PROD 产品、定价与税费 | component_source | candidate | NONE | — | id |
| m_tax_group | ods_fineract_m_tax_group | PROD 产品、定价与税费 | component_source | candidate | NONE | — | id |
| m_tax_group_mappings | ods_fineract_m_tax_group_mappings | PROD 产品、定价与税费 | bridge_source | candidate | NONE | — | id |
| m_tellers | ods_fineract_m_tellers | PAYM 支付结算 | standalone_dimension | human_reviewed | DIM | dim_teller | id |
| m_template | ods_fineract_m_template | OTHR 其它银行运营 | rule_reference | candidate | NONE | — | id |
| m_template_m_templatemappers | ods_fineract_m_template_m_templatemappers | OTHR 其它银行运营 | rule_reference | candidate | NONE | — | source row |
| m_templatemappers | ods_fineract_m_templatemappers | OTHR 其它银行运营 | rule_reference | candidate | NONE | — | id |
| m_trial_balance | ods_fineract_m_trial_balance | OTHR 其它银行运营 | snapshot_source | human_reviewed | DWD | dwd_gl_trial_balance_snapshot | office_id, account_id, entry_date |
| m_wc_breach_configuration | ods_fineract_m_wc_breach_configuration | WCLN 营运资金贷款 | rule_reference | candidate | NONE | — | id |
| m_wc_delinquency_configuration | ods_fineract_m_wc_delinquency_configuration | WCLN 营运资金贷款 | rule_reference | candidate | NONE | — | id |
| m_wc_loan | ods_fineract_m_wc_loan | WCLN 营运资金贷款 | standalone_dimension | human_reviewed | DIM | dim_wc_loan_account | id |
| m_wc_loan_account_locks | ods_fineract_m_wc_loan_account_locks | WCLN 营运资金贷款 | operational_only | candidate | NONE | — | loan_id |
| m_wc_loan_amortization_model | ods_fineract_m_wc_loan_amortization_model | WCLN 营运资金贷款 | component_source | candidate | NONE | — | id |
| m_wc_loan_balance | ods_fineract_m_wc_loan_balance | WCLN 营运资金贷款 | snapshot_source | human_reviewed | DWD | dwd_wc_loan_balance_snapshot | wc_loan_id, snapshot_date |
| m_wc_loan_breach_action | ods_fineract_m_wc_loan_breach_action | WCLN 营运资金贷款 | standalone_fact | human_reviewed | DWD | dwd_wc_breach_event | id |
| m_wc_loan_breach_reset_history | ods_fineract_m_wc_loan_breach_reset_history | WCLN 营运资金贷款 | component_source | candidate | NONE | — | id |
| m_wc_loan_breach_schedule | ods_fineract_m_wc_loan_breach_schedule | WCLN 营运资金贷款 | component_source | candidate | NONE | — | id |
| m_wc_loan_charge | ods_fineract_m_wc_loan_charge | WCLN 营运资金贷款 | component_source | candidate | NONE | — | id |
| m_wc_loan_delinquency_action | ods_fineract_m_wc_loan_delinquency_action | WCLN 营运资金贷款 | component_source | candidate | NONE | — | id |
| m_wc_loan_delinquency_range_schedule | ods_fineract_m_wc_loan_delinquency_range_schedule | WCLN 营运资金贷款 | component_source | candidate | NONE | — | id |
| m_wc_loan_disbursement_detail | ods_fineract_m_wc_loan_disbursement_detail | WCLN 营运资金贷款 | standalone_fact | human_reviewed | DWD | dwd_wc_loan_disbursement | id |
| m_wc_loan_near_breach_action | ods_fineract_m_wc_loan_near_breach_action | WCLN 营运资金贷款 | component_source | candidate | NONE | — | id |
| m_wc_loan_note | ods_fineract_m_wc_loan_note | WCLN 营运资金贷款 | component_source | candidate | NONE | — | id |
| m_wc_loan_originator_mapping | ods_fineract_m_wc_loan_originator_mapping | WCLN 营运资金贷款 | bridge_source | candidate | NONE | — | id |
| m_wc_loan_payment_allocation_rule | ods_fineract_m_wc_loan_payment_allocation_rule | WCLN 营运资金贷款 | rule_reference | candidate | NONE | — | id |
| m_wc_loan_period_payment_rate_change | ods_fineract_m_wc_loan_period_payment_rate_change | WCLN 营运资金贷款 | component_source | candidate | NONE | — | id |
| m_wc_loan_product | ods_fineract_m_wc_loan_product | WCLN 营运资金贷款 | standalone_dimension | human_reviewed | DIM | dim_wc_loan_product | id |
| m_wc_loan_product_configurable_attributes | ods_fineract_m_wc_loan_product_configurable_attributes | WCLN 营运资金贷款 | component_source | candidate | NONE | — | id |
| m_wc_loan_product_payment_allocation_rule | ods_fineract_m_wc_loan_product_payment_allocation_rule | WCLN 营运资金贷款 | rule_reference | candidate | NONE | — | id |
| m_wc_loan_range_delinquency_tag | ods_fineract_m_wc_loan_range_delinquency_tag | WCLN 营运资金贷款 | component_source | candidate | NONE | — | id |
| m_wc_loan_transaction | ods_fineract_m_wc_loan_transaction | WCLN 营运资金贷款 | standalone_fact | human_reviewed | DWD | dwd_wc_loan_transaction | id |
| m_wc_loan_transaction_allocation | ods_fineract_m_wc_loan_transaction_allocation | WCLN 营运资金贷款 | component_source | candidate | NONE | — | id |
| m_wc_loan_transaction_relation | ods_fineract_m_wc_loan_transaction_relation | WCLN 营运资金贷款 | bridge_source | candidate | NONE | — | id |
| m_wc_near_breach | ods_fineract_m_wc_near_breach | WCLN 营运资金贷款 | component_source | candidate | NONE | — | id |
| m_working_days | ods_fineract_m_working_days | ORGN 机构与员工 | standalone_dimension | human_reviewed | DIM | dim_working_day_rule | id |
| mix_taxonomy | ods_fineract_mix_taxonomy | OTHR 其它银行运营 | component_source | candidate | NONE | — | id |
| mix_taxonomy_mapping | ods_fineract_mix_taxonomy_mapping | OTHR 其它银行运营 | bridge_source | candidate | NONE | — | id |
| mix_xbrl_namespace | ods_fineract_mix_xbrl_namespace | OTHR 其它银行运营 | component_source | candidate | NONE | — | id |
| notification_generator | ods_fineract_notification_generator | CHNL 渠道与客户服务 | component_source | candidate | NONE | — | id |
| notification_mapper | ods_fineract_notification_mapper | CHNL 渠道与客户服务 | component_source | candidate | NONE | — | id |
| oauth_access_token | ods_fineract_oauth_access_token | OPER 平台运营与安全 | security_excluded | security_reviewed | NONE | — | source row |
| oauth_client_details | ods_fineract_oauth_client_details | OPER 平台运营与安全 | security_excluded | security_reviewed | NONE | — | client_id |
| oauth_refresh_token | ods_fineract_oauth_refresh_token | OPER 平台运营与安全 | security_excluded | security_reviewed | NONE | — | source row |
| ppi_likelihoods | ods_fineract_ppi_likelihoods | CHNL 渠道与客户服务 | component_source | candidate | NONE | — | id |
| ppi_likelihoods_ppi | ods_fineract_ppi_likelihoods_ppi | CHNL 渠道与客户服务 | component_source | candidate | NONE | — | id |
| ppi_scores | ods_fineract_ppi_scores | CHNL 渠道与客户服务 | component_source | candidate | NONE | — | id |
| r_enum_value | ods_fineract_r_enum_value | OTHR 其它银行运营 | component_source | candidate | NONE | — | enum_name, enum_id |
| ref_loan_transaction_processing_strategy | ods_fineract_ref_loan_transaction_processing_strategy | LOAN 贷款与信贷 | rule_reference | candidate | NONE | — | id |
| request_audit_table | ods_fineract_request_audit_table | RISK 风险、合规与审计 | security_excluded | security_reviewed | NONE | — | id |
| rpt_sequence | ods_fineract_rpt_sequence | OTHR 其它银行运营 | operational_only | candidate | NONE | — | id |
| scheduled_email_campaign | ods_fineract_scheduled_email_campaign | OTHR 其它银行运营 | security_excluded | security_reviewed | NONE | — | id |
| scheduled_email_configuration | ods_fineract_scheduled_email_configuration | REFR 公共参考与元数据 | security_excluded | security_reviewed | NONE | — | id |
| scheduled_email_messages_outbound | ods_fineract_scheduled_email_messages_outbound | OTHR 其它银行运营 | security_excluded | security_reviewed | NONE | — | id |
| scheduler_detail | ods_fineract_scheduler_detail | OPER 平台运营与安全 | operational_only | candidate | NONE | — | id |
| sms_campaign | ods_fineract_sms_campaign | CHNL 渠道与客户服务 | security_excluded | security_reviewed | NONE | — | id |
| sms_messages_outbound | ods_fineract_sms_messages_outbound | CHNL 渠道与客户服务 | component_source | candidate | NONE | — | id |
| stretchy_parameter | ods_fineract_stretchy_parameter | REFR 公共参考与元数据 | operational_only | candidate | NONE | — | id |
| stretchy_report | ods_fineract_stretchy_report | REFR 公共参考与元数据 | operational_only | candidate | NONE | — | id |
| stretchy_report_parameter | ods_fineract_stretchy_report_parameter | REFR 公共参考与元数据 | operational_only | candidate | NONE | — | id |
| twofactor_access_token | ods_fineract_twofactor_access_token | OPER 平台运营与安全 | security_excluded | security_reviewed | NONE | — | id |
| twofactor_configuration | ods_fineract_twofactor_configuration | REFR 公共参考与元数据 | security_excluded | security_reviewed | NONE | — | id |
| x_registered_table | ods_fineract_x_registered_table | OTHR 其它银行运营 | component_source | candidate | NONE | — | registered_table_name |
| x_table_column_code_mappings | ods_fineract_x_table_column_code_mappings | REFR 公共参考与元数据 | bridge_source | candidate | NONE | — | column_alias_name |
