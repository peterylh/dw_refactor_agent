-- Deterministic smoke data for Fineract m_calendar
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_calendar;

INSERT INTO retail_banking_dm.ods_fineract_m_calendar (
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
    `load_time`
) VALUES
    (
        1,
        'm_calendar_title_1',
        'm_calendar_description_1',
        'm_calendar_location_1',
        '2025-01-15',
        '2025-01-15',
        1,
        1,
        FALSE,
        'm_calendar_recurrence_1',
        1,
        1,
        1,
        1,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        '09:00:00',
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
