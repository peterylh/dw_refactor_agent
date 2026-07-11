-- Deterministic smoke data for Fineract m_wc_loan_account_locks
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_wc_loan_account_locks;

INSERT INTO retail_banking_dm.ods_fineract_m_wc_loan_account_locks (
    `loan_id`,
    `version`,
    `lock_owner`,
    `lock_placed_on`,
    `error`,
    `stacktrace`,
    `lock_placed_on_cob_business_date`,
    `load_time`
) VALUES
    (
        1,
        1,
        'm_wc_loan_account_locks_lock_owner_1',
        '2025-01-15 09:00:00',
        'm_wc_loan_account_locks_error_1',
        'm_wc_loan_account_locks_stacktrace_1',
        '2025-01-15',
        '2025-01-15 00:00:00'
    );
