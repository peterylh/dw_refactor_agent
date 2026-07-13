-- Deterministic smoke data for Fineract m_working_days
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_working_days;

INSERT INTO retail_banking_dm.ods_fineract_m_working_days (
    `id`,
    `recurrence`,
    `repayment_rescheduling_enum`,
    `extend_term_daily_repayments`,
    `extend_term_holiday_repayment`,
    `load_time`
) VALUES
    (
        1,
        'm_working_days_recurrence_1',
        1,
        FALSE,
        FALSE,
        '2025-01-15 00:00:00'
    );
