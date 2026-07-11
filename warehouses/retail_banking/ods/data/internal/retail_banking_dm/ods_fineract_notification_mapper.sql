-- Deterministic smoke data for Fineract notification_mapper
TRUNCATE TABLE retail_banking_dm.ods_fineract_notification_mapper;

INSERT INTO retail_banking_dm.ods_fineract_notification_mapper (
    `id`,
    `notification_id`,
    `user_id`,
    `is_read`,
    `created_at`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        FALSE,
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
