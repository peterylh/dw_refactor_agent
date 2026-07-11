-- Deterministic smoke data for Fineract m_holiday_office
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_holiday_office;

INSERT INTO retail_banking_dm.ods_fineract_m_holiday_office (
    `holiday_id`,
    `office_id`,
    `load_time`
) VALUES
    (
        1,
        1,
        '2025-01-15 00:00:00'
    );
