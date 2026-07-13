-- Human-reviewed semantic target: retail_banking_dm.dwd_wc_loan_transaction
TRUNCATE TABLE retail_banking_dm.dwd_wc_loan_transaction;

INSERT INTO retail_banking_dm.dwd_wc_loan_transaction (
    `id`,
    `wc_loan_id`,
    `payment_detail_id`,
    `classification_cv_id`,
    `external_id`,
    `transaction_type_id`,
    `transaction_date`,
    `submitted_on_date`,
    `transaction_amount`,
    `version`,
    `created_by`,
    `last_modified_by`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `is_reversed`,
    `reversal_external_id`,
    `reversed_on_date`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`wc_loan_id`,
    src.`payment_detail_id`,
    src.`classification_cv_id`,
    CASE WHEN src.`external_id` IS NULL THEN NULL ELSE SHA2(CAST(src.`external_id` AS STRING), 256) END AS `external_id`,
    src.`transaction_type_id`,
    src.`transaction_date`,
    src.`submitted_on_date`,
    src.`transaction_amount`,
    src.`version`,
    src.`created_by`,
    src.`last_modified_by`,
    src.`created_on_utc`,
    src.`last_modified_on_utc`,
    src.`is_reversed`,
    CASE WHEN src.`reversal_external_id` IS NULL THEN NULL ELSE SHA2(CAST(src.`reversal_external_id` AS STRING), 256) END AS `reversal_external_id`,
    src.`reversed_on_date`,
    DATE(src.`transaction_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_wc_loan_transaction AS src;
