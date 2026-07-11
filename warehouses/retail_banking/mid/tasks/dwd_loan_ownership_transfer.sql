SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_loan_ownership_transfer
TRUNCATE TABLE retail_banking_dm.dwd_loan_ownership_transfer;

INSERT INTO retail_banking_dm.dwd_loan_ownership_transfer (
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
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`owner_id`,
    CASE WHEN src.`external_id` IS NULL THEN NULL ELSE SHA2(CAST(src.`external_id` AS STRING), 256) END AS `external_id`,
    src.`status`,
    src.`purchase_price_ratio`,
    src.`settlement_date`,
    src.`effective_date_from`,
    src.`effective_date_to`,
    src.`created_by`,
    src.`created_on_utc`,
    src.`last_modified_by`,
    src.`last_modified_on_utc`,
    src.`external_loan_id`,
    src.`loan_id`,
    src.`sub_status`,
    src.`external_group_id`,
    src.`previous_owner_id`,
    DATE(src.`effective_date_from`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_external_asset_owner_transfer AS src;
