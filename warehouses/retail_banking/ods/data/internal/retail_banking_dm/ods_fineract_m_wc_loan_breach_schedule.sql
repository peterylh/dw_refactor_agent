-- Deterministic smoke data for Fineract m_wc_loan_breach_schedule
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_wc_loan_breach_schedule;

INSERT INTO retail_banking_dm.ods_fineract_m_wc_loan_breach_schedule (
    `id`,
    `wc_loan_id`,
    `period_number`,
    `from_date`,
    `to_date`,
    `number_of_days`,
    `min_payment_amount`,
    `paid_amount`,
    `outstanding_amount`,
    `near_breach`,
    `breach`,
    `created_by`,
    `last_modified_by`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `reset`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        '2025-01-15',
        '2025-01-15',
        1,
        100.000000,
        100.000000,
        100.000000,
        FALSE,
        FALSE,
        1,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        FALSE,
        '2025-01-15 00:00:00'
    );
