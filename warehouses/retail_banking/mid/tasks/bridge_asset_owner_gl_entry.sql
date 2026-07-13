SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.bridge_asset_owner_gl_entry
DELETE FROM retail_banking_dm.bridge_asset_owner_gl_entry
WHERE `business_date` = CAST(@etl_date AS DATE);
DELETE FROM retail_banking_dm.bridge_asset_owner_gl_entry
WHERE `business_date` IS NULL;

INSERT INTO retail_banking_dm.bridge_asset_owner_gl_entry (
    `id`,
    `journal_entry_id`,
    `owner_id`,
    `created_by`,
    `created_on_utc`,
    `last_modified_by`,
    `last_modified_on_utc`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`journal_entry_id`,
    src.`owner_id`,
    src.`created_by`,
    src.`created_on_utc`,
    src.`last_modified_by`,
    src.`last_modified_on_utc`,
    DATE(date_parent.`entry_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_external_asset_owner_journal_entry_mapping AS src
LEFT JOIN retail_banking_dm.ods_fineract_acc_gl_journal_entry AS date_parent
    ON src.`journal_entry_id` = date_parent.`id`
WHERE DATE(date_parent.`entry_date`) = CAST(@etl_date AS DATE)
   OR DATE(date_parent.`entry_date`) IS NULL;
