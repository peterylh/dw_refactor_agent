-- Deterministic smoke data for Fineract m_wc_loan_disbursement_detail
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_wc_loan_disbursement_detail;

INSERT INTO retail_banking_dm.ods_fineract_m_wc_loan_disbursement_detail (
    `id`,
    `wc_loan_id`,
    `expected_disburse_date`,
    `expected_amount`,
    `expected_maturity_date`,
    `actual_disburse_date`,
    `actual_amount`,
    `disbursedon_userid`,
    `load_time`
) VALUES
    (
        1,
        1,
        '2025-01-15',
        100.000000,
        '2025-01-15',
        '2025-01-15',
        100.000000,
        1,
        '2025-01-15 00:00:00'
    );
