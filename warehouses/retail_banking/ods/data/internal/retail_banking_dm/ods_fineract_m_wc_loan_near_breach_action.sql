-- Deterministic smoke data for Fineract m_wc_loan_near_breach_action
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_wc_loan_near_breach_action;

INSERT INTO retail_banking_dm.ods_fineract_m_wc_loan_near_breach_action (
    `id`,
    `wc_loan_id`,
    `action`,
    `threshold`,
    `frequency`,
    `frequency_type`,
    `created_by`,
    `last_modified_by`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `load_time`
) VALUES
    (
        1,
        1,
        'm_wc_loan_near_breach_action_action_1',
        1,
        1,
        'm_wc_loan_near_breach_action_frequency_type_1',
        1,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
