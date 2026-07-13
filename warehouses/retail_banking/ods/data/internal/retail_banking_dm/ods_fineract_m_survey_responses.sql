-- Deterministic smoke data for Fineract m_survey_responses
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_survey_responses;

INSERT INTO retail_banking_dm.ods_fineract_m_survey_responses (
    `id`,
    `question_id`,
    `a_text`,
    `a_value`,
    `sequence_no`,
    `load_time`
) VALUES
    (
        1,
        1,
        'm_survey_responses_a_text_1',
        1,
        1,
        '2025-01-15 00:00:00'
    );
