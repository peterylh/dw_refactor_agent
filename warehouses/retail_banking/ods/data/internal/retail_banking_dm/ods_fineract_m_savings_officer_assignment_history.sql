-- Deterministic smoke data for Fineract m_savings_officer_assignment_history
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_savings_officer_assignment_history;

INSERT INTO retail_banking_dm.ods_fineract_m_savings_officer_assignment_history (
    `id`,
    `account_id`,
    `savings_officer_id`,
    `start_date`,
    `end_date`,
    `created_by`,
    `created_date`,
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
        '2025-01-15',
        '2025-01-15',
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
