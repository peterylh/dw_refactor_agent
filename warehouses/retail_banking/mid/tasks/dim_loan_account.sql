SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dim_loan_account
TRUNCATE TABLE retail_banking_dm.dim_loan_account;

INSERT INTO retail_banking_dm.dim_loan_account (
    `id`,
    `account_no`,
    `external_id`,
    `client_id`,
    `group_id`,
    `product_id`,
    `fund_id`,
    `loan_type_enum`,
    `currency_code`,
    `loan_transaction_strategy_code`,
    `etl_time`
)
SELECT
    src.`id`,
    CASE WHEN src.`account_no` IS NULL THEN NULL ELSE SHA2(CAST(src.`account_no` AS STRING), 256) END AS `account_no`,
    CASE WHEN src.`external_id` IS NULL THEN NULL ELSE SHA2(CAST(src.`external_id` AS STRING), 256) END AS `external_id`,
    src.`client_id`,
    src.`group_id`,
    src.`product_id`,
    src.`fund_id`,
    src.`loan_type_enum`,
    src.`currency_code`,
    src.`loan_transaction_strategy_code`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_loan AS src;
