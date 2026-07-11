-- Deterministic smoke data for Fineract glim_accounts
TRUNCATE TABLE retail_banking_dm.ods_fineract_glim_accounts;

INSERT INTO retail_banking_dm.ods_fineract_glim_accounts (
    `id`,
    `group_id`,
    `account_number`,
    `principal_amount`,
    `child_accounts_count`,
    `accepting_child`,
    `loan_status_id`,
    `application_id`,
    `load_time`
) VALUES
    (
        1,
        1,
        'A000000001',
        100.000000,
        1,
        FALSE,
        1,
        1,
        '2025-01-15 00:00:00'
    );
