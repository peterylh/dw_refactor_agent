-- Deterministic smoke data for Fineract m_external_asset_owner_transfer_details
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_external_asset_owner_transfer_details;

INSERT INTO retail_banking_dm.ods_fineract_m_external_asset_owner_transfer_details (
    `id`,
    `asset_owner_transfer_id`,
    `total_outstanding_derived`,
    `principal_outstanding_derived`,
    `interest_outstanding_derived`,
    `fee_charges_outstanding_derived`,
    `penalty_charges_outstanding_derived`,
    `total_overpaid_derived`,
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
        100.000000,
        100.000000,
        100.000000,
        100.000000,
        1,
        1,
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
