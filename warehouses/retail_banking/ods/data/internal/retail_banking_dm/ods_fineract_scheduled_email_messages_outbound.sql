-- Deterministic smoke data for Fineract scheduled_email_messages_outbound
TRUNCATE TABLE retail_banking_dm.ods_fineract_scheduled_email_messages_outbound;

INSERT INTO retail_banking_dm.ods_fineract_scheduled_email_messages_outbound (
    `id`,
    `group_id`,
    `client_id`,
    `staff_id`,
    `email_campaign_id`,
    `status_enum`,
    `email_address`,
    `email_subject`,
    `message`,
    `campaign_name`,
    `submittedon_date`,
    `error_message`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        1,
        1,
        'user1@example.com',
        'user1@example.com',
        'scheduled_email_messages_outbound_message_1',
        'scheduled_email_messages_outbound_campaign_name_1',
        '2025-01-15',
        'scheduled_email_messages_outbound_error_message_1',
        '2025-01-15 00:00:00'
    );
