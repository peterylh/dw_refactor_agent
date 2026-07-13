-- Human-reviewed semantic target: retail_banking_dm.dim_accounting_rule
TRUNCATE TABLE retail_banking_dm.dim_accounting_rule;

INSERT INTO retail_banking_dm.dim_accounting_rule (
    `id`,
    `name`,
    `office_id`,
    `debit_account_id`,
    `allow_multiple_debits`,
    `credit_account_id`,
    `allow_multiple_credits`,
    `description`,
    `system_defined`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`name`,
    src.`office_id`,
    src.`debit_account_id`,
    src.`allow_multiple_debits`,
    src.`credit_account_id`,
    src.`allow_multiple_credits`,
    src.`description`,
    src.`system_defined`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_acc_accounting_rule AS src;
