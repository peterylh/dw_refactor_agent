SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_survey_response
TRUNCATE TABLE retail_banking_dm.dwd_survey_response;

INSERT INTO retail_banking_dm.dwd_survey_response (
    `id`,
    `survey_id`,
    `question_id`,
    `response_id`,
    `user_id`,
    `client_id`,
    `created_on`,
    `a_value`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`survey_id`,
    src.`question_id`,
    src.`response_id`,
    src.`user_id`,
    src.`client_id`,
    src.`created_on`,
    src.`a_value`,
    DATE(src.`created_on`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_survey_scorecards AS src;
