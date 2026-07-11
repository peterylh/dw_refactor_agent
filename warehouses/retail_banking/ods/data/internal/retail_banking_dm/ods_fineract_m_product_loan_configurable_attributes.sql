-- Deterministic smoke data for Fineract m_product_loan_configurable_attributes
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_product_loan_configurable_attributes;

INSERT INTO retail_banking_dm.ods_fineract_m_product_loan_configurable_attributes (
    `id`,
    `loan_product_id`,
    `amortization_method_enum`,
    `interest_method_enum`,
    `loan_transaction_strategy_code`,
    `interest_calculated_in_period_enum`,
    `arrearstolerance_amount`,
    `repay_every`,
    `moratorium`,
    `grace_on_arrears_ageing`,
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
        FALSE,
        FALSE,
        FALSE,
        '2025-01-15 00:00:00'
    );
