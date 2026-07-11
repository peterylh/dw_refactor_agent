-- Deterministic smoke data for Fineract m_loan_arrears_aging
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loan_arrears_aging;

INSERT INTO retail_banking_dm.ods_fineract_m_loan_arrears_aging (
    `loan_id`,
    `principal_overdue_derived`,
    `interest_overdue_derived`,
    `fee_charges_overdue_derived`,
    `penalty_charges_overdue_derived`,
    `total_overdue_derived`,
    `overdue_since_date_derived`,
    `load_time`
) VALUES
    (
        1,
        100.000000,
        100.000000,
        100.000000,
        100.000000,
        1,
        '2025-01-15',
        '2025-01-15 00:00:00'
    );
