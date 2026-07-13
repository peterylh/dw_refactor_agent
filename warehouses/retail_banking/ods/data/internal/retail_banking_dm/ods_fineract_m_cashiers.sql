-- Deterministic smoke data for Fineract m_cashiers
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_cashiers;

INSERT INTO retail_banking_dm.ods_fineract_m_cashiers (
    `id`,
    `staff_id`,
    `teller_id`,
    `description`,
    `start_date`,
    `end_date`,
    `start_time`,
    `end_time`,
    `full_day`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        'm_cashiers_description_1',
        '2025-01-15',
        '2025-01-15',
        'm_cashiers',
        'm_cashiers',
        FALSE,
        '2025-01-15 00:00:00'
    );
