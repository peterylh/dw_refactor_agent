-- Deterministic smoke data for Fineract m_trial_balance
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_trial_balance;

INSERT INTO retail_banking_dm.ods_fineract_m_trial_balance (
    `office_id`,
    `account_id`,
    `amount`,
    `entry_date`,
    `created_date`,
    `closing_balance`,
    `load_time`
) VALUES
    (
        1,
        1,
        100.000000,
        '2025-01-15',
        '2025-01-15',
        100.000000,
        '2025-01-15 00:00:00'
    );
