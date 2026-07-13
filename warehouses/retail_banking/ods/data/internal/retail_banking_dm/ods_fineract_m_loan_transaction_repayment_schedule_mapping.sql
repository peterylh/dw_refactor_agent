-- Deterministic smoke data for Fineract m_loan_transaction_repayment_schedule_mapping
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loan_transaction_repayment_schedule_mapping;

INSERT INTO retail_banking_dm.ods_fineract_m_loan_transaction_repayment_schedule_mapping (
    `id`,
    `loan_transaction_id`,
    `loan_repayment_schedule_id`,
    `amount`,
    `principal_portion_derived`,
    `interest_portion_derived`,
    `fee_charges_portion_derived`,
    `penalty_charges_portion_derived`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        100.000000,
        100.000000,
        100.000000,
        100.000000,
        100.000000,
        '2025-01-15 00:00:00'
    );
