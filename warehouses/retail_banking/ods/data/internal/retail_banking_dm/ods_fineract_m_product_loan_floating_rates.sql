-- Deterministic smoke data for Fineract m_product_loan_floating_rates
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_product_loan_floating_rates;

INSERT INTO retail_banking_dm.ods_fineract_m_product_loan_floating_rates (
    `id`,
    `loan_product_id`,
    `floating_rates_id`,
    `interest_rate_differential`,
    `min_differential_lending_rate`,
    `default_differential_lending_rate`,
    `max_differential_lending_rate`,
    `is_floating_interest_rate_calculation_allowed`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        100.000000,
        1,
        1,
        1,
        FALSE,
        '2025-01-15 00:00:00'
    );
