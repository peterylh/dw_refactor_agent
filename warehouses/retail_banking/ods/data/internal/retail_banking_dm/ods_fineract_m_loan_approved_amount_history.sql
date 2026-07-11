-- Deterministic smoke data for Fineract m_loan_approved_amount_history
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loan_approved_amount_history;

INSERT INTO retail_banking_dm.ods_fineract_m_loan_approved_amount_history (
    `id`,
    `loan_id`,
    `new_approved_amount`,
    `old_approved_amount`,
    `created_by`,
    `created_on_utc`,
    `last_modified_by`,
    `last_modified_on_utc`,
    `load_time`
) VALUES
    (
        1,
        1,
        100.000000,
        100.000000,
        1,
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
