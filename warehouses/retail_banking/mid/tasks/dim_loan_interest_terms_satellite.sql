SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dim_loan_interest_terms_satellite
TRUNCATE TABLE retail_banking_dm.dim_loan_interest_terms_satellite;

INSERT INTO retail_banking_dm.dim_loan_interest_terms_satellite (
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
    `etl_time`
)
SELECT
    src.`id`,
    src.`loan_id`,
    src.`compound_type_enum`,
    src.`reschedule_strategy_enum`,
    src.`rest_frequency_type_enum`,
    src.`rest_frequency_interval`,
    src.`compounding_frequency_type_enum`,
    src.`compounding_frequency_interval`,
    src.`rest_frequency_nth_day_enum`,
    src.`rest_frequency_on_day`,
    src.`rest_frequency_weekday_enum`,
    src.`compounding_frequency_nth_day_enum`,
    src.`compounding_frequency_on_day`,
    src.`is_compounding_to_be_posted_as_transaction`,
    src.`compounding_frequency_weekday_enum`,
    src.`allow_compounding_on_eod`,
    src.`disallow_interest_calc_on_past_due`,
    src.`pre_close_interest_calculation_strategy`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_loan_recalculation_details AS src;
