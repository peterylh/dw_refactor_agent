-- Deterministic smoke data for Fineract m_wc_loan_product_configurable_attributes
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_wc_loan_product_configurable_attributes;

INSERT INTO retail_banking_dm.ods_fineract_m_wc_loan_product_configurable_attributes (
    `id`,
    `wc_loan_product_id`,
    `delinquency_bucket_classification_overridable`,
    `discount_default_overridable`,
    `period_payment_frequency_overridable`,
    `period_payment_frequency_type_overridable`,
    `breach_overridable`,
    `load_time`
) VALUES
    (
        1,
        1,
        FALSE,
        FALSE,
        FALSE,
        FALSE,
        FALSE,
        '2025-01-15 00:00:00'
    );
