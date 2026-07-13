-- Deterministic smoke data for Fineract m_survey_questions
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_survey_questions;

INSERT INTO retail_banking_dm.ods_fineract_m_survey_questions (
    `id`,
    `survey_id`,
    `component_key`,
    `a_key`,
    `a_text`,
    `description`,
    `sequence_no`,
    `load_time`
) VALUES
    (
        1,
        1,
        'm_survey_questions_component_key',
        'm_survey_questions_a_key_1',
        'm_survey_questions_a_text_1',
        'm_survey_questions_description_1',
        1,
        '2025-01-15 00:00:00'
    );
