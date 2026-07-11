-- Deterministic smoke data for Fineract m_wc_loan_amortization_model
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_wc_loan_amortization_model;

INSERT INTO retail_banking_dm.ods_fineract_m_wc_loan_amortization_model (
    `id`,
    `version`,
    `loan_id`,
    `json_model`,
    `business_date`,
    `json_model_version`,
    `last_modified_on_utc`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        '{}',
        '2025-01-15',
        '{}',
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
