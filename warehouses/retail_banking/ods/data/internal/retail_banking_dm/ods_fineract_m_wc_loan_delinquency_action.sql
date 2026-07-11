-- Deterministic smoke data for Fineract m_wc_loan_delinquency_action
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_wc_loan_delinquency_action;

INSERT INTO retail_banking_dm.ods_fineract_m_wc_loan_delinquency_action (
    `id`,
    `wc_loan_id`,
    `action`,
    `start_date`,
    `end_date`,
    `created_by`,
    `last_modified_by`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `minimum_payment`,
    `minimum_payment_type`,
    `frequency`,
    `frequency_type`,
    `load_time`
) VALUES
    (
        1,
        1,
        'm_wc_loan_delinquency_action_action_1',
        '2025-01-15',
        '2025-01-15',
        1,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        1,
        'm_wc_loan_delinquency_action_minimum_payment_type_',
        1,
        'm_wc_loan_delinquency_action_frequency_type_1',
        '2025-01-15 00:00:00'
    );
