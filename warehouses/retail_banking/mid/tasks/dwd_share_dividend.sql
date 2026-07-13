SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_share_dividend
DELETE FROM retail_banking_dm.dwd_share_dividend
WHERE `business_date` = CAST(@etl_date AS DATE);
DELETE FROM retail_banking_dm.dwd_share_dividend
WHERE `business_date` IS NULL;

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
WHERE DATE(date_parent.`dividend_period_end_date`) = CAST(@etl_date AS DATE)
   OR DATE(date_parent.`dividend_period_end_date`) IS NULL;
