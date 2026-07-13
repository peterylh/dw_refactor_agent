-- Deterministic smoke data for Fineract m_surveys
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_surveys;

INSERT INTO retail_banking_dm.ods_fineract_m_surveys (
    `id`,
    `a_key`,
    `a_name`,
    `description`,
    `country_code`,
    `valid_from`,
    `valid_to`,
    `load_time`
) VALUES
    (
        1,
        'm_surveys_a_key_1',
        'm_surveys_a_name_1',
        'm_surveys_description_1',
        'US',
        '2025-01-15',
        '2025-01-15',
        '2025-01-15 00:00:00'
    );
