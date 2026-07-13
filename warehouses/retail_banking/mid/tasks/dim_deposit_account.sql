-- Human-reviewed semantic target: retail_banking_dm.dim_deposit_account
TRUNCATE TABLE retail_banking_dm.dim_deposit_account;

INSERT INTO retail_banking_dm.dim_deposit_account (
    `id`,
    `account_no`,
    `external_id`,
    `client_id`,
    `group_id`,
    `product_id`,
    `account_type_enum`,
    `deposit_type_enum`,
    `currency_code`,
    `etl_time`
)
SELECT
    src.`id`,
    CASE WHEN src.`account_no` IS NULL THEN NULL ELSE SHA2(CAST(src.`account_no` AS STRING), 256) END AS `account_no`,
    CASE WHEN src.`external_id` IS NULL THEN NULL ELSE SHA2(CAST(src.`external_id` AS STRING), 256) END AS `external_id`,
    src.`client_id`,
    src.`group_id`,
    src.`product_id`,
    src.`account_type_enum`,
    src.`deposit_type_enum`,
    src.`currency_code`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_savings_account AS src;
