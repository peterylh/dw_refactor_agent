-- Deterministic smoke data for Fineract m_loan_account_locks
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loan_account_locks;

INSERT INTO retail_banking_dm.ods_fineract_m_loan_account_locks (
    `loan_id`,
    `lock_owner`,
    `error`,
    `version`,
    `stacktrace`,
    `lock_placed_on`,
    `lock_placed_on_cob_business_date`,
    `load_time`
) VALUES
    (
        1,
        'm_loan_account_locks_lock_owner_1',
        'm_loan_account_locks_error_1',
        1,
        'm_loan_account_locks_stacktrace_1',
        '2025-01-15 09:00:00',
        '2025-01-15',
        '2025-01-15 00:00:00'
    );
