-- Deterministic smoke data for Fineract m_loan_topup
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loan_topup;

INSERT INTO retail_banking_dm.ods_fineract_m_loan_topup (
    `id`,
    `loan_id`,
    `closure_loan_id`,
    `account_transfer_details_id`,
    `topup_amount`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        100.000000,
        '2025-01-15 00:00:00'
    );
