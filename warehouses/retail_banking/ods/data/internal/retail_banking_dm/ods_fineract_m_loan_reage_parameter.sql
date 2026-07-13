-- Deterministic smoke data for Fineract m_loan_reage_parameter
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loan_reage_parameter;

INSERT INTO retail_banking_dm.ods_fineract_m_loan_reage_parameter (
    `id`,
    `frequency_type`,
    `number_of_installments`,
    `start_date`,
    `created_by`,
    `last_modified_by`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `loan_transaction_id`,
    `frequency_number`,
    `interest_handling_type`,
    `reage_reason_code_value_id`,
    `load_time`
) VALUES
    (
        1,
        'm_loan_reage_parameter_frequency_type_1',
        1,
        '2025-01-15',
        1,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        1,
        1,
        'm_loan_reage_parameter_interest_handling',
        1,
        '2025-01-15 00:00:00'
    );
