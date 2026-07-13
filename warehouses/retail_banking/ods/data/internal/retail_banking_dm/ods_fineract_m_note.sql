-- Deterministic smoke data for Fineract m_note
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_note;

INSERT INTO retail_banking_dm.ods_fineract_m_note (
    `id`,
    `client_id`,
    `group_id`,
    `loan_id`,
    `loan_transaction_id`,
    `savings_account_id`,
    `savings_account_transaction_id`,
    `share_account_id`,
    `note_type_enum`,
    `note`,
    `created_date`,
    `created_by`,
    `lastmodified_date`,
    `last_modified_by`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        'm_note_note_1',
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
