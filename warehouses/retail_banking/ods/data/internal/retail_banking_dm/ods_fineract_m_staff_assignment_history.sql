-- Deterministic smoke data for Fineract m_staff_assignment_history
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_staff_assignment_history;

INSERT INTO retail_banking_dm.ods_fineract_m_staff_assignment_history (
    `id`,
    `centre_id`,
    `staff_id`,
    `start_date`,
    `end_date`,
    `createdby_id`,
    `created_date`,
    `lastmodified_date`,
    `lastmodifiedby_id`,
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
        '2025-01-15 00:00:00'
    );
