SET @etl_end_date = COALESCE(@etl_end_date, CURDATE());
SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date);

-- Human-reviewed semantic target: retail_banking_dm.dwd_loan_ownership_transfer_detail
TRUNCATE TABLE retail_banking_dm.dwd_loan_ownership_transfer_detail;

INSERT INTO retail_banking_dm.dwd_loan_ownership_transfer_detail (
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
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`asset_owner_transfer_id`,
    src.`total_outstanding_derived`,
    src.`principal_outstanding_derived`,
    src.`interest_outstanding_derived`,
    src.`fee_charges_outstanding_derived`,
    src.`penalty_charges_outstanding_derived`,
    src.`total_overpaid_derived`,
    src.`created_by`,
    src.`created_on_utc`,
    src.`last_modified_by`,
    src.`last_modified_on_utc`,
    DATE(date_parent.`effective_date_from`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_external_asset_owner_transfer_details AS src
LEFT JOIN retail_banking_dm.ods_fineract_m_external_asset_owner_transfer AS date_parent
    ON src.`asset_owner_transfer_id` = date_parent.`id`
WHERE (DATE(date_parent.`effective_date_from`) IS NULL OR (DATE(date_parent.`effective_date_from`) >= CAST(@etl_start_date AS DATE) AND DATE(date_parent.`effective_date_from`) <= CAST(@etl_end_date AS DATE)));
