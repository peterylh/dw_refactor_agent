SET @etl_end_date = COALESCE(@etl_end_date, CURDATE());
SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date);

-- Human-reviewed semantic target: retail_banking_dm.dwd_share_dividend
TRUNCATE TABLE retail_banking_dm.dwd_share_dividend;

INSERT INTO retail_banking_dm.dwd_share_dividend (
    `id`,
    `dividend_pay_out_id`,
    `account_id`,
    `amount`,
    `status`,
    `savings_transaction_id`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`dividend_pay_out_id`,
    src.`account_id`,
    src.`amount`,
    src.`status`,
    src.`savings_transaction_id`,
    DATE(date_parent.`dividend_period_end_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_share_account_dividend_details AS src
LEFT JOIN retail_banking_dm.ods_fineract_m_share_product_dividend_pay_out AS date_parent
    ON src.`dividend_pay_out_id` = date_parent.`id`
WHERE (DATE(date_parent.`dividend_period_end_date`) IS NULL OR (DATE(date_parent.`dividend_period_end_date`) >= CAST(@etl_start_date AS DATE) AND DATE(date_parent.`dividend_period_end_date`) <= CAST(@etl_end_date AS DATE)));
