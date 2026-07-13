-- Deterministic smoke data for Fineract notification_generator
TRUNCATE TABLE retail_banking_dm.ods_fineract_notification_generator;

INSERT INTO retail_banking_dm.ods_fineract_notification_generator (
    `id`,
    `object_type`,
    `object_identifier`,
    `action`,
    `actor`,
    `is_system_generated`,
    `notification_content`,
    `created_at`,
    `load_time`
) VALUES
    (
        1,
        'notification_generator_object_type_1',
        1,
        'notification_generator_action_1',
        1,
        FALSE,
        'notification_generator_notification_content_1',
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
