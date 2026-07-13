-- Human-reviewed semantic target: retail_banking_dm.dim_share_account
TRUNCATE TABLE retail_banking_dm.dim_share_account;

INSERT INTO retail_banking_dm.dim_share_account (
    `id`,
    `account_no`,
    `external_id`,
    `client_id`,
    `product_id`,
    `savings_account_id`,
    `currency_code`,
    `etl_time`
)
SELECT
    src.`id`,
    CASE WHEN src.`account_no` IS NULL THEN NULL ELSE SHA2(CAST(src.`account_no` AS STRING), 256) END AS `account_no`,
    CASE WHEN src.`external_id` IS NULL THEN NULL ELSE SHA2(CAST(src.`external_id` AS STRING), 256) END AS `external_id`,
    src.`client_id`,
    src.`product_id`,
    src.`savings_account_id`,
    src.`currency_code`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_share_account AS src;
