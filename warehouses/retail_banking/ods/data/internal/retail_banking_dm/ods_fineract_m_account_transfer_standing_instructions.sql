-- Deterministic smoke data for Fineract m_account_transfer_standing_instructions
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_account_transfer_standing_instructions;

INSERT INTO retail_banking_dm.ods_fineract_m_account_transfer_standing_instructions (
    `id`,
    `name`,
    `account_transfer_details_id`,
    `priority`,
    `status`,
    `instruction_type`,
    `amount`,
    `valid_from`,
    `valid_till`,
    `recurrence_type`,
    `recurrence_frequency`,
    `recurrence_interval`,
    `recurrence_on_day`,
    `recurrence_on_month`,
    `last_run_date`,
    `load_time`
) VALUES
    (
        1,
        'Synthetic m_account_transfer_standing_instructions 1',
        1,
        1,
        300,
        1,
        100.000000,
        '2025-01-15',
        '2025-01-15',
        1,
        1,
        1,
        1,
        1,
        '2025-01-15',
        '2025-01-15 00:00:00'
    );
