-- Deterministic smoke data for Fineract m_external_asset_owner
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_external_asset_owner;

INSERT INTO retail_banking_dm.ods_fineract_m_external_asset_owner (
    `id`,
    `external_id`,
    `created_by`,
    `created_on_utc`,
    `last_modified_by`,
    `last_modified_on_utc`,
    `load_time`
) VALUES
    (
        1,
        '00000000-0000-4000-8000-000000000001',
        1,
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
