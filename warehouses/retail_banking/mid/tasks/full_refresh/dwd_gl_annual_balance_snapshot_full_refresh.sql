SET @etl_end_date = COALESCE(@etl_end_date, CURDATE());
SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date);

-- Human-reviewed semantic target: retail_banking_dm.dwd_gl_annual_balance_snapshot
TRUNCATE TABLE retail_banking_dm.dwd_gl_annual_balance_snapshot;

INSERT INTO retail_banking_dm.dwd_gl_annual_balance_snapshot (
    `id`,
    `gl_code`,
    `product_id`,
    `office_id`,
    `opening_balance_amount`,
    `currency_code`,
    `owner_external_id`,
    `manual_entry`,
    `year_end_date`,
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
    src.`gl_code`,
    src.`product_id`,
    src.`office_id`,
    src.`opening_balance_amount`,
    src.`currency_code`,
    src.`owner_external_id`,
    src.`manual_entry`,
    src.`year_end_date`,
    src.`created_by`,
    src.`created_on_utc`,
    src.`last_modified_by`,
    src.`last_modified_on_utc`,
    src.`originator_external_ids`,
    DATE(src.`year_end_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_acc_gl_journal_entry_annual_summary AS src
WHERE (DATE(src.`year_end_date`) IS NULL OR (DATE(src.`year_end_date`) >= CAST(@etl_start_date AS DATE) AND DATE(src.`year_end_date`) <= CAST(@etl_end_date AS DATE)));
