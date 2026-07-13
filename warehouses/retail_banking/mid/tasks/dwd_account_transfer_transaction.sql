SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_account_transfer_transaction
DELETE FROM retail_banking_dm.dwd_account_transfer_transaction
WHERE `business_date` = CAST(@etl_date AS DATE);
DELETE FROM retail_banking_dm.dwd_account_transfer_transaction
WHERE `business_date` IS NULL;

INSERT INTO retail_banking_dm.dwd_account_transfer_transaction (
    `id`,
    `account_transfer_details_id`,
    `from_savings_transaction_id`,
    `from_loan_transaction_id`,
    `to_savings_transaction_id`,
    `to_loan_transaction_id`,
    `is_reversed`,
    `transaction_date`,
    `currency_code`,
    `currency_digits`,
    `currency_multiplesof`,
    `amount`,
    `description`,
    `from_office_id`,
    `to_office_id`,
    `transfer_type`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`account_transfer_details_id`,
    src.`from_savings_transaction_id`,
    src.`from_loan_transaction_id`,
    src.`to_savings_transaction_id`,
    src.`to_loan_transaction_id`,
    src.`is_reversed`,
    src.`transaction_date`,
    src.`currency_code`,
    src.`currency_digits`,
    src.`currency_multiplesof`,
    src.`amount`,
    CASE WHEN src.`description` IS NULL THEN NULL ELSE '***' END AS `description`,
    enrichment_parent.`from_office_id` AS `from_office_id`,
    enrichment_parent.`to_office_id` AS `to_office_id`,
    enrichment_parent.`transfer_type` AS `transfer_type`,
    DATE(src.`transaction_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_account_transfer_transaction AS src
LEFT JOIN retail_banking_dm.ods_fineract_m_account_transfer_details AS enrichment_parent
    ON src.`account_transfer_details_id` = enrichment_parent.`id`
WHERE DATE(src.`transaction_date`) = CAST(@etl_date AS DATE)
   OR DATE(src.`transaction_date`) IS NULL;
