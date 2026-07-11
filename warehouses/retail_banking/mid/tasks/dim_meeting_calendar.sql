SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dim_meeting_calendar
TRUNCATE TABLE retail_banking_dm.dim_meeting_calendar;

INSERT INTO retail_banking_dm.dim_meeting_calendar (
    `id`,
    `title`,
    `description`,
    `location`,
    `start_date`,
    `end_date`,
    `duration`,
    `calendar_type_enum`,
    `repeating`,
    `recurrence`,
    `remind_by_enum`,
    `first_reminder`,
    `second_reminder`,
    `created_by`,
    `last_modified_by`,
    `created_date`,
    `lastmodified_date`,
    `meeting_time`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`title`,
    src.`description`,
    src.`location`,
    src.`start_date`,
    src.`end_date`,
    src.`duration`,
    src.`calendar_type_enum`,
    src.`repeating`,
    src.`recurrence`,
    src.`remind_by_enum`,
    src.`first_reminder`,
    src.`second_reminder`,
    src.`created_by`,
    src.`last_modified_by`,
    src.`created_date`,
    src.`lastmodified_date`,
    src.`meeting_time`,
    src.`created_on_utc`,
    src.`last_modified_on_utc`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_calendar AS src;
