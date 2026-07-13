-- Deterministic smoke data for Fineract m_product_loan_recalculation_details
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_product_loan_recalculation_details;

INSERT INTO retail_banking_dm.ods_fineract_m_product_loan_recalculation_details (
    `id`,
    `product_id`,
    `compound_type_enum`,
    `reschedule_strategy_enum`,
    `rest_frequency_type_enum`,
    `rest_frequency_interval`,
    `arrears_based_on_original_schedule`,
    `pre_close_interest_calculation_strategy`,
    `compounding_frequency_type_enum`,
    `compounding_frequency_interval`,
    `rest_frequency_nth_day_enum`,
    `rest_frequency_on_day`,
    `rest_frequency_weekday_enum`,
    `compounding_frequency_nth_day_enum`,
    `compounding_frequency_on_day`,
    `compounding_frequency_weekday_enum`,
    `is_compounding_to_be_posted_as_transaction`,
    `allow_compounding_on_eod`,
    `disallow_interest_calc_on_past_due`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        1,
        1,
        FALSE,
        100.000000,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        FALSE,
        FALSE,
        FALSE,
        '2025-01-15 00:00:00'
    );
