-- Deterministic smoke data for Fineract m_loan_amortization_allocation_mapping
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loan_amortization_allocation_mapping;

INSERT INTO retail_banking_dm.ods_fineract_m_loan_amortization_allocation_mapping (
    `id`,
    `loan_id`,
    `base_loan_transaction_id`,
    `date`,
    `amortization_loan_transaction_id`,
    `amortization_type`,
    `amount`,
    `created_by`,
    `created_on_utc`,
    `last_modified_by`,
    `last_modified_on_utc`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        '2025-01-15',
        1,
        'm_loan_amortization_',
        100.000000,
        1,
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
