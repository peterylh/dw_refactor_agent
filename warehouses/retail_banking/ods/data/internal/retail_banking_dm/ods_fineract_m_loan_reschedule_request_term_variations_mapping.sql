-- Deterministic smoke data for Fineract m_loan_reschedule_request_term_variations_mapping
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loan_reschedule_request_term_variations_mapping;

INSERT INTO retail_banking_dm.ods_fineract_m_loan_reschedule_request_term_variations_mapping (
    `id`,
    `loan_reschedule_request_id`,
    `loan_term_variations_id`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        '2025-01-15 00:00:00'
    );
