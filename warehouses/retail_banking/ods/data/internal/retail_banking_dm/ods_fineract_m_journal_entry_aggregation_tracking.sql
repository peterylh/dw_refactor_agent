-- Deterministic smoke data for Fineract m_journal_entry_aggregation_tracking
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_journal_entry_aggregation_tracking;

INSERT INTO retail_banking_dm.ods_fineract_m_journal_entry_aggregation_tracking (
    `id`,
    `aggregated_on_date_from`,
    `aggregated_on_date_to`,
    `submitted_on_date`,
    `job_execution_id`,
    `created_by`,
    `created_on_utc`,
    `last_modified_by`,
    `last_modified_on_utc`,
    `load_time`
) VALUES
    (
        1,
        '2025-01-15',
        '2025-01-15',
        '2025-01-15',
        1,
        1,
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
