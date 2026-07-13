-- Deterministic smoke data for Fineract acc_accounting_rule
TRUNCATE TABLE retail_banking_dm.ods_fineract_acc_accounting_rule;

INSERT INTO retail_banking_dm.ods_fineract_acc_accounting_rule (
    `id`,
    `name`,
    `office_id`,
    `debit_account_id`,
    `allow_multiple_debits`,
    `credit_account_id`,
    `allow_multiple_credits`,
    `description`,
    `system_defined`,
    `load_time`
) VALUES
    (
        1,
        'Synthetic acc_accounting_rule 1',
        1,
        1,
        FALSE,
        1,
        FALSE,
        'acc_accounting_rule_description_1',
        FALSE,
        '2025-01-15 00:00:00'
    );
