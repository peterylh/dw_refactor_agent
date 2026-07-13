-- Human-reviewed semantic target: retail_banking_dm.dwd_gl_aggregation_run
TRUNCATE TABLE retail_banking_dm.dwd_gl_aggregation_run;

INSERT INTO retail_banking_dm.dwd_gl_aggregation_run (
    `id`,
    `aggregated_on_date_from`,
    `aggregated_on_date_to`,
    `submitted_on_date`,
    `job_execution_id`,
    `created_by`,
    `created_on_utc`,
    `last_modified_by`,
    `last_modified_on_utc`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`aggregated_on_date_from`,
    src.`aggregated_on_date_to`,
    src.`submitted_on_date`,
    src.`job_execution_id`,
    src.`created_by`,
    src.`created_on_utc`,
    src.`last_modified_by`,
    src.`last_modified_on_utc`,
    DATE(src.`aggregated_on_date_from`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_journal_entry_aggregation_tracking AS src;
