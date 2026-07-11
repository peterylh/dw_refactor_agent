-- Deterministic smoke data for Fineract m_hook_registered_events
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_hook_registered_events;

INSERT INTO retail_banking_dm.ods_fineract_m_hook_registered_events (
    `id`,
    `hook_id`,
    `entity_name`,
    `action_name`,
    `load_time`
) VALUES
    (
        1,
        1,
        'm_hook_registered_events_entity_name_1',
        'm_hook_registered_events_action_name_1',
        '2025-01-15 00:00:00'
    );
