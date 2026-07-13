-- Deterministic smoke data for Fineract m_loan_reschedule_request
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loan_reschedule_request;

INSERT INTO retail_banking_dm.ods_fineract_m_loan_reschedule_request (
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
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        '2025-01-15',
        FALSE,
        1,
        'm_loan_reschedule_request_reschedule_reason_comment_1',
        '2025-01-15',
        1,
        '2025-01-15',
        1,
        '2025-01-15',
        1,
        '2025-01-15 00:00:00'
    );
