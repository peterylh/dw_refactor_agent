-- Deterministic smoke data for Fineract m_account_transfer_standing_instructions_history
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_account_transfer_standing_instructions_history;

INSERT INTO retail_banking_dm.ods_fineract_m_account_transfer_standing_instructions_history (
    `id`,
    `standing_instruction_id`,
    `status`,
    `execution_time`,
    `amount`,
    `error_log`,
    `load_time`
) VALUES
    (
        1,
        1,
        'm_account_transfer_s',
        '2025-01-15 09:00:00',
        100.000000,
        'm_account_transfer_standing_instructions_history_error_log_1',
        '2025-01-15 00:00:00'
    );
