-- Deterministic smoke data for Fineract m_external_asset_owner_transfer_journal_entry_mapping
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_external_asset_owner_transfer_journal_entry_mapping;

INSERT INTO retail_banking_dm.ods_fineract_m_external_asset_owner_transfer_journal_entry_mapping (
    `id`,
    `journal_entry_id`,
    `owner_transfer_id`,
    `created_by`,
    `created_on_utc`,
    `last_modified_by`,
    `last_modified_on_utc`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
