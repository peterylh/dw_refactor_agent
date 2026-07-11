-- Deterministic smoke data for Fineract m_loan_reamortization_parameter
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loan_reamortization_parameter;

INSERT INTO retail_banking_dm.ods_fineract_m_loan_reamortization_parameter (
    `id`,
    `loan_transaction_id`,
    `interest_handling_type`,
    `reamortization_reason_code_value_id`,
    `created_by`,
    `last_modified_by`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `load_time`
) VALUES
    (
        1,
        1,
        'm_loan_reamortization_parameter_interest',
        1,
        1,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
