-- Deterministic smoke data for Fineract m_calendar_history
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_calendar_history;

INSERT INTO retail_banking_dm.ods_fineract_m_calendar_history (
    `id`,
    `calendar_id`,
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
    `load_time`
) VALUES
    (
        1,
        1,
        'm_calendar_history_title_1',
        'm_calendar_history_description_1',
        'm_calendar_history_location_1',
        '2025-01-15',
        '2025-01-15',
        1,
        1,
        FALSE,
        'm_calendar_history_recurrence_1',
        1,
        1,
        1,
        '2025-01-15 00:00:00'
    );
