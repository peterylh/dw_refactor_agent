-- Deterministic smoke data for Fineract m_loan_charge_paid_by
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loan_charge_paid_by;

INSERT INTO retail_banking_dm.ods_fineract_m_loan_charge_paid_by (
    `id`,
    `loan_transaction_id`,
    `loan_charge_id`,
    `amount`,
    `installment_number`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        100.000000,
        1,
        '2025-01-15 00:00:00'
    );
