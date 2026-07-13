-- Deterministic smoke data for Fineract m_wc_loan_period_payment_rate_change
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_wc_loan_period_payment_rate_change;

INSERT INTO retail_banking_dm.ods_fineract_m_wc_loan_period_payment_rate_change (
    `id`,
    `wc_loan_id`,
    `effective_date`,
    `previous_rate`,
    `new_rate`,
    `is_reversed`,
    `reversed_on_date`,
    `created_by`,
    `last_modified_by`,
    `version`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `load_time`
) VALUES
    (
        1,
        1,
        '2025-01-15',
        1,
        1,
        FALSE,
        '2025-01-15',
        1,
        1,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
