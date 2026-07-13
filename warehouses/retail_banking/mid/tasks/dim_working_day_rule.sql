-- Human-reviewed semantic target: retail_banking_dm.dim_working_day_rule
TRUNCATE TABLE retail_banking_dm.dim_working_day_rule;

INSERT INTO retail_banking_dm.dim_working_day_rule (
    `id`,
    `recurrence`,
    `repayment_rescheduling_enum`,
    `extend_term_daily_repayments`,
    `extend_term_holiday_repayment`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`recurrence`,
    src.`repayment_rescheduling_enum`,
    src.`extend_term_daily_repayments`,
    src.`extend_term_holiday_repayment`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_working_days AS src;
