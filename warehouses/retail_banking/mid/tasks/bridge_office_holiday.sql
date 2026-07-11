SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.bridge_office_holiday
TRUNCATE TABLE retail_banking_dm.bridge_office_holiday;

INSERT INTO retail_banking_dm.bridge_office_holiday (
    `holiday_id`,
    `office_id`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`holiday_id`,
    src.`office_id`,
    DATE(date_parent.`from_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_holiday_office AS src
LEFT JOIN retail_banking_dm.ods_fineract_m_holiday AS date_parent
    ON src.`holiday_id` = date_parent.`id`;
