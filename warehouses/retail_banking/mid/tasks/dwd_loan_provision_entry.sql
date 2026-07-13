-- Provisioning detail enriched with its run header and references
TRUNCATE TABLE retail_banking_dm.dwd_loan_provision_entry;

INSERT INTO retail_banking_dm.dwd_loan_provision_entry (
    `id`,
    `history_id`,
    `criteria_id`,
    `currency_code`,
    `office_id`,
    `product_id`,
    `category_id`,
    `overdue_in_days`,
    `reseve_amount`,
    `liability_account`,
    `expense_account`,
    `provision_date`,
    `journal_entry_created`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`history_id`,
    src.`criteria_id`,
    src.`currency_code`,
    src.`office_id`,
    src.`product_id`,
    src.`category_id`,
    src.`overdue_in_days`,
    src.`reseve_amount`,
    src.`liability_account`,
    src.`expense_account`,
    DATE(run.`created_date`) AS `provision_date`,
    run.`journal_entry_created`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_loanproduct_provisioning_entry AS src
LEFT JOIN retail_banking_dm.ods_fineract_m_provisioning_history AS run
    ON src.`history_id` = run.`id`
LEFT JOIN retail_banking_dm.ods_fineract_m_office AS office
    ON src.`office_id` = office.`id`
LEFT JOIN retail_banking_dm.ods_fineract_m_provision_category AS category
    ON src.`category_id` = category.`id`
LEFT JOIN retail_banking_dm.ods_fineract_acc_gl_account AS liability_account
    ON src.`liability_account` = liability_account.`id`
LEFT JOIN retail_banking_dm.ods_fineract_acc_gl_account AS expense_account
    ON src.`expense_account` = expense_account.`id`;
