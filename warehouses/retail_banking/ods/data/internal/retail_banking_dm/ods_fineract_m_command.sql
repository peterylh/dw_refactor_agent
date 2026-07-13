-- Deterministic smoke data for Fineract m_command
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_command;

INSERT INTO retail_banking_dm.ods_fineract_m_command (
    `id`,
    `created_at`,
    `command_id`,
    `tenant_id`,
    `initiated_by_username`,
    `request`,
    `updated_at`,
    `executed_at`,
    `approved_at`,
    `rejected_at`,
    `idempotency_key`,
    `executed_by_username`,
    `approved_by_username`,
    `rejected_by_username`,
    `ip_address`,
    `state`,
    `response`,
    `error`,
    `load_time`
) VALUES
    (
        1,
        '2025-01-15 09:00:00',
        'm_command_command_id_1',
        'm_command_tenant_id_1',
        'm_command_initiated_by_username_1',
        'm_command_request_1',
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        'm_command_idempotency_key_1',
        'm_command_executed_by_username_1',
        'm_command_approved_by_username_1',
        'm_command_rejected_by_username_1',
        'm_command_ip_address_1',
        'm_command_state_1',
        'm_command_response_1',
        'm_command_error_1',
        '2025-01-15 00:00:00'
    );
