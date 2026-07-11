-- Deterministic smoke data for Fineract m_wc_loan_breach_reset_history
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_wc_loan_breach_reset_history;

INSERT INTO retail_banking_dm.ods_fineract_m_wc_loan_breach_reset_history (
    `id`,
    `breach_action_id`,
    `breach_schedule_id`,
    `outstanding_amount`,
    `breach`,
    `near_breach`,
    `created_by`,
    `last_modified_by`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `min_payment_amount`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        100.000000,
        FALSE,
        FALSE,
        1,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        100.000000,
        '2025-01-15 00:00:00'
    );
