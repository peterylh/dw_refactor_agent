-- Human-reviewed semantic target: retail_banking_dm.dim_holiday
TRUNCATE TABLE retail_banking_dm.dim_holiday;

INSERT INTO retail_banking_dm.dim_holiday (
    `id`,
    `name`,
    `from_date`,
    `to_date`,
    `repayments_rescheduled_to`,
    `status_enum`,
    `processed`,
    `description`,
    `rescheduling_type`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`name`,
    src.`from_date`,
    src.`to_date`,
    src.`repayments_rescheduled_to`,
    src.`status_enum`,
    src.`processed`,
    src.`description`,
    src.`rescheduling_type`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_holiday AS src;
