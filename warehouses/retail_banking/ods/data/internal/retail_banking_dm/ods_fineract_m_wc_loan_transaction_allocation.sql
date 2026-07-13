-- Deterministic smoke data for Fineract m_wc_loan_transaction_allocation
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_wc_loan_transaction_allocation;

INSERT INTO retail_banking_dm.ods_fineract_m_wc_loan_transaction_allocation (
    `id`,
    `wc_loan_transaction_id`,
    `principal_portion`,
    `fee_charges_portion`,
    `penalty_charges_portion`,
    `version`,
    `created_by`,
    `last_modified_by`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `load_time`
) VALUES
    (
        1,
        1,
        100.000000,
        100.000000,
        100.000000,
        1,
        1,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
