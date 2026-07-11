-- Deterministic smoke data for Fineract m_holiday
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_holiday;

INSERT INTO retail_banking_dm.ods_fineract_m_holiday (
    `id`,
    `name`,
    `from_date`,
    `to_date`,
    `repayments_rescheduled_to`,
    `status_enum`,
    `processed`,
    `description`,
    `rescheduling_type`,
    `load_time`
) VALUES
    (
        1,
        'Synthetic m_holiday 1',
        '2025-01-15',
        '2025-01-15',
        '2025-01-15',
        1,
        FALSE,
        'm_holiday_description_1',
        1,
        '2025-01-15 00:00:00'
    );
