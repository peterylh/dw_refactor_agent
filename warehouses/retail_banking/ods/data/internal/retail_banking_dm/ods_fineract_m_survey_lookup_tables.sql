-- Deterministic smoke data for Fineract m_survey_lookup_tables
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_survey_lookup_tables;

INSERT INTO retail_banking_dm.ods_fineract_m_survey_lookup_tables (
    `id`,
    `survey_id`,
    `a_key`,
    `description`,
    `value_from`,
    `value_to`,
    `score`,
    `load_time`
) VALUES
    (
        1,
        1,
        'm_survey_lookup_tables_a_key_1',
        1,
        1,
        1,
        1,
        '2025-01-15 00:00:00'
    );
