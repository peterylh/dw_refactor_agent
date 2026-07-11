-- Deterministic smoke data for Fineract m_calendar_instance
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_calendar_instance;

INSERT INTO retail_banking_dm.ods_fineract_m_calendar_instance (
    `id`,
    `calendar_id`,
    `entity_id`,
    `entity_type_enum`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        '2025-01-15 00:00:00'
    );
