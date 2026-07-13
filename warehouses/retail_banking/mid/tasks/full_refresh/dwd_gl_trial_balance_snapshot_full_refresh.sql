SET @etl_end_date = COALESCE(@etl_end_date, CURDATE());
SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date);

-- Human-reviewed semantic target: retail_banking_dm.dwd_gl_trial_balance_snapshot
TRUNCATE TABLE retail_banking_dm.dwd_gl_trial_balance_snapshot;

INSERT INTO retail_banking_dm.dwd_gl_trial_balance_snapshot (
    `office_id`,
    `account_id`,
    `amount`,
    `entry_date`,
    `created_date`,
    `closing_balance`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`office_id`,
    src.`account_id`,
    src.`amount`,
    src.`entry_date`,
    src.`created_date`,
    src.`closing_balance`,
    DATE(src.`entry_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_trial_balance AS src
WHERE (DATE(src.`entry_date`) IS NULL OR (DATE(src.`entry_date`) >= CAST(@etl_start_date AS DATE) AND DATE(src.`entry_date`) <= CAST(@etl_end_date AS DATE)));
