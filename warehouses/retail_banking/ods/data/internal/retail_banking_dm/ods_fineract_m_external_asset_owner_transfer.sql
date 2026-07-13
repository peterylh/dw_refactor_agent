-- Deterministic smoke data for Fineract m_external_asset_owner_transfer
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_external_asset_owner_transfer;

INSERT INTO retail_banking_dm.ods_fineract_m_external_asset_owner_transfer (
    `id`,
    `owner_id`,
    `external_id`,
    `status`,
    `purchase_price_ratio`,
    `settlement_date`,
    `effective_date_from`,
    `effective_date_to`,
    `created_by`,
    `created_on_utc`,
    `last_modified_by`,
    `last_modified_on_utc`,
    `external_loan_id`,
    `loan_id`,
    `sub_status`,
    `external_group_id`,
    `previous_owner_id`,
    `load_time`
) VALUES
    (
        1,
        1,
        '00000000-0000-4000-8000-000000000001',
        'm_external_asset_owner_transfer_status_1',
        'm_external_asset_owner_transfer_purchase_price_rat',
        '2025-01-15',
        '2025-01-15',
        '2025-01-15',
        1,
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 09:00:00',
        'm_external_asset_owner_transfer_external_loan_id_1',
        1,
        'm_external_asset_owner_transfer_sub_status_1',
        'm_external_asset_owner_transfer_external_group_id_1',
        1,
        '2025-01-15 00:00:00'
    );
