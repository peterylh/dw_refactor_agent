SET @etl_end_date = COALESCE(@etl_end_date, CURDATE());
SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date);

-- Human-reviewed semantic target: retail_banking_dm.dwd_loan_buy_down_fee_balance
TRUNCATE TABLE retail_banking_dm.dwd_loan_buy_down_fee_balance;

INSERT INTO retail_banking_dm.dwd_loan_buy_down_fee_balance (
    `id`,
    `version`,
    `loan_id`,
    `loan_transaction_id`,
    `amount`,
    `date`,
    `unrecognized_amount`,
    `charged_off_amount`,
    `amount_adjustment`,
    `created_by`,
    `created_on_utc`,
    `last_modified_by`,
    `last_modified_on_utc`,
    `is_deleted`,
    `is_closed`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`version`,
    src.`loan_id`,
    src.`loan_transaction_id`,
    src.`amount`,
    src.`date`,
    src.`unrecognized_amount`,
    src.`charged_off_amount`,
    src.`amount_adjustment`,
    src.`created_by`,
    src.`created_on_utc`,
    src.`last_modified_by`,
    src.`last_modified_on_utc`,
    src.`is_deleted`,
    src.`is_closed`,
    DATE(src.`date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_loan_buy_down_fee_balance AS src
WHERE (DATE(src.`date`) IS NULL OR (DATE(src.`date`) >= CAST(@etl_start_date AS DATE) AND DATE(src.`date`) <= CAST(@etl_end_date AS DATE)));
