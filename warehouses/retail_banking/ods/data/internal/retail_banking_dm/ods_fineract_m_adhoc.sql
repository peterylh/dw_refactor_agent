-- Deterministic smoke data for Fineract m_adhoc
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_adhoc;

INSERT INTO retail_banking_dm.ods_fineract_m_adhoc (
    `id`,
    `name`,
    `query`,
    `table_name`,
    `table_fields`,
    `email`,
    `is_active`,
    `created_date`,
    `createdby_id`,
    `lastmodifiedby_id`,
    `lastmodified_date`,
    `report_run_frequency_code`,
    `report_run_every`,
    `last_run`,
    `load_time`
) VALUES
    (
        1,
        'Synthetic m_adhoc 1',
        'm_adhoc_query_1',
        'm_adhoc_table_name_1',
        'm_adhoc_table_fields_1',
        'user1@example.com',
        FALSE,
        '2025-01-15 09:00:00',
        1,
        1,
        '2025-01-15 09:00:00',
        1,
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
