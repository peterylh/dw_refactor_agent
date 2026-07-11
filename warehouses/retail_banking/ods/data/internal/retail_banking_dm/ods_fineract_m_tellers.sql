-- Deterministic smoke data for Fineract m_tellers
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_tellers;

INSERT INTO retail_banking_dm.ods_fineract_m_tellers (
    `id`,
    `office_id`,
    `debit_account_id`,
    `credit_account_id`,
    `name`,
    `description`,
    `valid_from`,
    `valid_to`,
    `state`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        'Synthetic m_tellers 1',
        'm_tellers_description_1',
        '2025-01-15',
        '2025-01-15',
        1,
        '2025-01-15 00:00:00'
    );
