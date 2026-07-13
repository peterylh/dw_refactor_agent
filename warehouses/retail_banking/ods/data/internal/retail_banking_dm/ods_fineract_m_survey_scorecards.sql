-- Deterministic smoke data for Fineract m_survey_scorecards
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_survey_scorecards;

INSERT INTO retail_banking_dm.ods_fineract_m_survey_scorecards (
    `id`,
    `survey_id`,
    `question_id`,
    `response_id`,
    `user_id`,
    `client_id`,
    `created_on`,
    `a_value`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        1,
        1,
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 00:00:00'
    );
