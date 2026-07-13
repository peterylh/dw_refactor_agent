-- Deterministic smoke data for Fineract sms_messages_outbound
TRUNCATE TABLE retail_banking_dm.ods_fineract_sms_messages_outbound;

INSERT INTO retail_banking_dm.ods_fineract_sms_messages_outbound (
    `id`,
    `group_id`,
    `client_id`,
    `staff_id`,
    `status_enum`,
    `mobile_no`,
    `message`,
    `campaign_id`,
    `external_id`,
    `submittedon_date`,
    `delivered_on_date`,
    `is_notification`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        1,
        '15500000001',
        'sms_messages_outbound_message_1',
        1,
        '00000000-0000-4000-8000-000000000001',
        '2025-01-15',
        '2025-01-15 09:00:00',
        FALSE,
        '2025-01-15 00:00:00'
    );
