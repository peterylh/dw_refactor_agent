-- Deterministic smoke data for Fineract m_provisioning_history
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_provisioning_history;

INSERT INTO retail_banking_dm.ods_fineract_m_provisioning_history (
    `id`,
    `journal_entry_created`,
    `createdby_id`,
    `created_date`,
    `lastmodifiedby_id`,
    `lastmodified_date`,
    `load_time`
) VALUES
    (
        1,
        FALSE,
        1,
        '2025-01-15',
        1,
        '2025-01-15',
        '2025-01-15 00:00:00'
    );
