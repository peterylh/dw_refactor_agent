-- Deterministic smoke data for Fineract m_loan_disbursement_detail
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loan_disbursement_detail;

INSERT INTO retail_banking_dm.ods_fineract_m_loan_disbursement_detail (
    `id`,
    `loan_id`,
    `expected_disburse_date`,
    `disbursedon_date`,
    `principal`,
    `net_disbursal_amount`,
    `is_reversed`,
    `load_time`
) VALUES
    (
        1,
        1,
        '2025-01-15',
        '2025-01-15',
        100.000000,
        100.000000,
        FALSE,
        '2025-01-15 00:00:00'
    );
