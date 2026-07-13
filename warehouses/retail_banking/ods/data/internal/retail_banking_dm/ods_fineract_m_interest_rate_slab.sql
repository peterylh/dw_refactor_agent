-- Deterministic smoke data for Fineract m_interest_rate_slab
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_interest_rate_slab;

INSERT INTO retail_banking_dm.ods_fineract_m_interest_rate_slab (
    `id`,
    `interest_rate_chart_id`,
    `description`,
    `period_type_enum`,
    `from_period`,
    `to_period`,
    `amount_range_from`,
    `amount_range_to`,
    `annual_interest_rate`,
    `currency_code`,
    `load_time`
) VALUES
    (
        1,
        1,
        'm_interest_rate_slab_description_1',
        1,
        1,
        1,
        100.000000,
        100.000000,
        100.000000,
        'USD',
        '2025-01-15 00:00:00'
    );
