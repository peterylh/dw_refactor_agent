-- Deterministic smoke data for Fineract m_repayment_with_post_dated_checks
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_repayment_with_post_dated_checks;

INSERT INTO retail_banking_dm.ods_fineract_m_repayment_with_post_dated_checks (
    `id`,
    `check_no`,
    `amount`,
    `loan_id`,
    `repayment_id`,
    `account_no`,
    `bank_name`,
    `repayment_date`,
    `status`,
    `load_time`
) VALUES
    (
        1,
        1,
        100.000000,
        1,
        1,
        1,
        'm_repayment_with_post_dated_checks_bank_name_1',
        '2025-01-15',
        300,
        '2025-01-15 00:00:00'
    );
