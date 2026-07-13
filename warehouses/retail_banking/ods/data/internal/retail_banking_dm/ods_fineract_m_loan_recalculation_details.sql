-- Deterministic smoke data for Fineract m_loan_recalculation_details
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_loan_recalculation_details;

INSERT INTO retail_banking_dm.ods_fineract_m_loan_recalculation_details (
    `id`,
    `loan_id`,
    `compound_type_enum`,
    `reschedule_strategy_enum`,
    `rest_frequency_type_enum`,
    `rest_frequency_interval`,
    `compounding_frequency_type_enum`,
    `compounding_frequency_interval`,
    `rest_frequency_nth_day_enum`,
    `rest_frequency_on_day`,
    `rest_frequency_weekday_enum`,
    `compounding_frequency_nth_day_enum`,
    `compounding_frequency_on_day`,
    `is_compounding_to_be_posted_as_transaction`,
    `compounding_frequency_weekday_enum`,
    `allow_compounding_on_eod`,
    `disallow_interest_calc_on_past_due`,
    `pre_close_interest_calculation_strategy`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        FALSE,
        1,
        FALSE,
        FALSE,
        100.000000,
        '2025-01-15 00:00:00'
    );
