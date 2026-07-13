-- Deterministic smoke data for Fineract m_journal_entry_aggregation_summary
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_journal_entry_aggregation_summary;

INSERT INTO retail_banking_dm.ods_fineract_m_journal_entry_aggregation_summary (
    `id`,
    `gl_account_id`,
    `product_id`,
    `office_id`,
    `entity_type_enum`,
    `aggregated_on_date`,
    `submitted_on_date`,
    `external_owner_id`,
    `debit_amount`,
    `credit_amount`,
    `manual_entry`,
    `job_execution_id`,
    `created_by`,
    `created_on_utc`,
    `last_modified_by`,
    `last_modified_on_utc`,
    `originator_external_ids`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        1,
        '2025-01-15',
        '2025-01-15',
        1,
        100.000000,
        100.000000,
        FALSE,
        1,
        1,
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 09:00:00',
        '00000000-0000-4000-8000-000000000001',
        '2025-01-15 00:00:00'
    );
