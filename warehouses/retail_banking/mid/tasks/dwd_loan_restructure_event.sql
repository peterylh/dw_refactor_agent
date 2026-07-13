-- Human-reviewed semantic target: retail_banking_dm.dwd_loan_restructure_event
TRUNCATE TABLE retail_banking_dm.dwd_loan_restructure_event;

INSERT INTO retail_banking_dm.dwd_loan_restructure_event (
    `id`,
    `loan_id`,
    `status_enum`,
    `reschedule_from_installment`,
    `reschedule_from_date`,
    `recalculate_interest`,
    `reschedule_reason_cv_id`,
    `reschedule_reason_comment`,
    `submitted_on_date`,
    `submitted_by_user_id`,
    `approved_on_date`,
    `approved_by_user_id`,
    `rejected_on_date`,
    `rejected_by_user_id`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`loan_id`,
    src.`status_enum`,
    src.`reschedule_from_installment`,
    src.`reschedule_from_date`,
    src.`recalculate_interest`,
    src.`reschedule_reason_cv_id`,
    CASE WHEN src.`reschedule_reason_comment` IS NULL THEN NULL ELSE '***' END AS `reschedule_reason_comment`,
    src.`submitted_on_date`,
    src.`submitted_by_user_id`,
    src.`approved_on_date`,
    src.`approved_by_user_id`,
    src.`rejected_on_date`,
    src.`rejected_by_user_id`,
    DATE(src.`submitted_on_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_loan_reschedule_request AS src;
