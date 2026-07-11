SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.bridge_loan_transaction_relation
TRUNCATE TABLE retail_banking_dm.bridge_loan_transaction_relation;

INSERT INTO retail_banking_dm.bridge_loan_transaction_relation (
    `id`,
    `from_loan_transaction_id`,
    `to_loan_transaction_id`,
    `relation_type_enum`,
    `created_by`,
    `created_on_utc`,
    `last_modified_by`,
    `last_modified_on_utc`,
    `to_loan_charge_id`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`from_loan_transaction_id`,
    src.`to_loan_transaction_id`,
    src.`relation_type_enum`,
    src.`created_by`,
    src.`created_on_utc`,
    src.`last_modified_by`,
    src.`last_modified_on_utc`,
    src.`to_loan_charge_id`,
    DATE(date_parent.`transaction_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_loan_transaction_relation AS src
LEFT JOIN retail_banking_dm.ods_fineract_m_loan_transaction AS date_parent
    ON src.`from_loan_transaction_id` = date_parent.`id`;
