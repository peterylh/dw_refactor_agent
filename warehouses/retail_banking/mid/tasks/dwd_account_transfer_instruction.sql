SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_account_transfer_instruction
TRUNCATE TABLE retail_banking_dm.dwd_account_transfer_instruction;

INSERT INTO retail_banking_dm.dwd_account_transfer_instruction (
    `id`,
    `from_office_id`,
    `to_office_id`,
    `from_client_id`,
    `to_client_id`,
    `from_savings_account_id`,
    `to_savings_account_id`,
    `from_loan_account_id`,
    `to_loan_account_id`,
    `transfer_type`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`from_office_id`,
    src.`to_office_id`,
    src.`from_client_id`,
    src.`to_client_id`,
    src.`from_savings_account_id`,
    src.`to_savings_account_id`,
    src.`from_loan_account_id`,
    src.`to_loan_account_id`,
    src.`transfer_type`,
    DATE(date_parent.`business_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_account_transfer_details AS src
LEFT JOIN (
    SELECT `account_transfer_details_id`, MIN(`transaction_date`) AS `business_date`
    FROM retail_banking_dm.ods_fineract_m_account_transfer_transaction
    GROUP BY `account_transfer_details_id`
) AS date_parent
    ON src.`id` = date_parent.`account_transfer_details_id`;
