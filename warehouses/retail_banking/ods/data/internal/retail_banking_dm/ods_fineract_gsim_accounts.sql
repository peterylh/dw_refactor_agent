-- Deterministic smoke data for Fineract gsim_accounts
TRUNCATE TABLE retail_banking_dm.ods_fineract_gsim_accounts;

INSERT INTO retail_banking_dm.ods_fineract_gsim_accounts (
    `id`,
    `group_id`,
    `account_number`,
    `parent_deposit`,
    `child_accounts_count`,
    `accepting_child`,
    `savings_status_id`,
    `application_id`,
    `load_time`
) VALUES
    (
        1,
        1,
        'A000000001',
        1,
        1,
        FALSE,
        1,
        1,
        '2025-01-15 00:00:00'
    );
