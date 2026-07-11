-- Deterministic smoke data for Fineract m_wc_loan_delinquency_range_schedule
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_wc_loan_delinquency_range_schedule;

INSERT INTO retail_banking_dm.ods_fineract_m_wc_loan_delinquency_range_schedule (
    `id`,
    `wc_loan_id`,
    `period_number`,
    `from_date`,
    `to_date`,
    `expected_amount`,
    `paid_amount`,
    `outstanding_amount`,
    `min_payment_criteria_met`,
    `created_by`,
    `last_modified_by`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `delinquent_days`,
    `delinquent_amount`,
    `version`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        '2025-01-15',
        '2025-01-15',
        100.000000,
        100.000000,
        100.000000,
        FALSE,
        1,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        1,
        100.000000,
        1,
        '2025-01-15 00:00:00'
    );
