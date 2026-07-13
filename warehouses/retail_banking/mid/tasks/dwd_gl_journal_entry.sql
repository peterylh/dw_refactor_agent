SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_gl_journal_entry
DELETE FROM retail_banking_dm.dwd_gl_journal_entry
WHERE `business_date` = CAST(@etl_date AS DATE);
DELETE FROM retail_banking_dm.dwd_gl_journal_entry
WHERE `business_date` IS NULL;

INSERT INTO retail_banking_dm.dwd_gl_journal_entry (
    `id`,
    `account_id`,
    `office_id`,
    `reversal_id`,
    `currency_code`,
    `transaction_id`,
    `loan_transaction_id`,
    `savings_transaction_id`,
    `client_transaction_id`,
    `reversed`,
    `ref_num`,
    `manual_entry`,
    `entry_date`,
    `type_enum`,
    `amount`,
    `description`,
    `entity_type_enum`,
    `entity_id`,
    `created_by`,
    `last_modified_by`,
    `created_date`,
    `lastmodified_date`,
    `is_running_balance_calculated`,
    `office_running_balance`,
    `organization_running_balance`,
    `payment_details_id`,
    `share_transaction_id`,
    `transaction_date`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `submitted_on_date`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`account_id`,
    src.`office_id`,
    src.`reversal_id`,
    src.`currency_code`,
    src.`transaction_id`,
    src.`loan_transaction_id`,
    src.`savings_transaction_id`,
    src.`client_transaction_id`,
    src.`reversed`,
    src.`ref_num`,
    src.`manual_entry`,
    src.`entry_date`,
    src.`type_enum`,
    src.`amount`,
    src.`description`,
    src.`entity_type_enum`,
    src.`entity_id`,
    src.`created_by`,
    src.`last_modified_by`,
    src.`created_date`,
    src.`lastmodified_date`,
    src.`is_running_balance_calculated`,
    src.`office_running_balance`,
    src.`organization_running_balance`,
    src.`payment_details_id`,
    src.`share_transaction_id`,
    src.`transaction_date`,
    src.`created_on_utc`,
    src.`last_modified_on_utc`,
    src.`submitted_on_date`,
    DATE(src.`entry_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_acc_gl_journal_entry AS src
WHERE DATE(src.`entry_date`) = CAST(@etl_date AS DATE)
   OR DATE(src.`entry_date`) IS NULL;
