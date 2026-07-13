SET @etl_end_date = COALESCE(@etl_end_date, CURDATE());
SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date);

-- Human-reviewed semantic target: retail_banking_dm.dwd_group_meeting_attendance
TRUNCATE TABLE retail_banking_dm.dwd_group_meeting_attendance;

INSERT INTO retail_banking_dm.dwd_group_meeting_attendance (
    `id`,
    `client_id`,
    `meeting_id`,
    `attendance_type_enum`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`client_id`,
    src.`meeting_id`,
    src.`attendance_type_enum`,
    DATE(date_parent.`meeting_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_client_attendance AS src
LEFT JOIN retail_banking_dm.ods_fineract_m_meeting AS date_parent
    ON src.`meeting_id` = date_parent.`id`
WHERE (DATE(date_parent.`meeting_date`) IS NULL OR (DATE(date_parent.`meeting_date`) >= CAST(@etl_start_date AS DATE) AND DATE(date_parent.`meeting_date`) <= CAST(@etl_end_date AS DATE)));
