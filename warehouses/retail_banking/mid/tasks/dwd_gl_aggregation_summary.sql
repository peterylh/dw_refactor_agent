-- Human-reviewed semantic target: retail_banking_dm.dwd_gl_aggregation_summary
TRUNCATE TABLE retail_banking_dm.dwd_gl_aggregation_summary;

INSERT INTO retail_banking_dm.dwd_gl_aggregation_summary (
    `id`,
    `gl_account_id`,
    `product_id`,
    `office_id`,
    `entity_type_enum`,
    `aggregated_on_date`,
    `submitted_on_date`,
    `external_owner_id`,
    `debit_amount`,
    `credit_amount`,
    `manual_entry`,
    `job_execution_id`,
    `created_by`,
    `created_on_utc`,
    `last_modified_by`,
    `last_modified_on_utc`,
    `originator_external_ids`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`gl_account_id`,
    src.`product_id`,
    src.`office_id`,
    src.`entity_type_enum`,
    src.`aggregated_on_date`,
    src.`submitted_on_date`,
    src.`external_owner_id`,
    src.`debit_amount`,
    src.`credit_amount`,
    src.`manual_entry`,
    src.`job_execution_id`,
    src.`created_by`,
    src.`created_on_utc`,
    src.`last_modified_by`,
    src.`last_modified_on_utc`,
    src.`originator_external_ids`,
    DATE(src.`aggregated_on_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_journal_entry_aggregation_summary AS src;
