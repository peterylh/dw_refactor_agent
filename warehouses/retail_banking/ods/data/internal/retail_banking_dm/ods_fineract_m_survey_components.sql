-- Deterministic smoke data for Fineract m_survey_components
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_survey_components;

INSERT INTO retail_banking_dm.ods_fineract_m_survey_components (
    `id`,
    `survey_id`,
    `a_key`,
    `a_text`,
    `description`,
    `sequence_no`,
    `load_time`
) VALUES
    (
        1,
        1,
        'm_survey_components_a_key_1',
        'm_survey_components_a_text_1',
        'm_survey_components_description_1',
        1,
        '2025-01-15 00:00:00'
    );
