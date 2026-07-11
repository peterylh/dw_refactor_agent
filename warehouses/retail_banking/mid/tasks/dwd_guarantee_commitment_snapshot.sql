SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_guarantee_commitment_snapshot
TRUNCATE TABLE retail_banking_dm.dwd_guarantee_commitment_snapshot;

INSERT INTO retail_banking_dm.dwd_guarantee_commitment_snapshot (
    `id`,
    `guarantor_id`,
    `account_associations_id`,
    `amount`,
    `amount_released_derived`,
    `amount_remaining_derived`,
    `amount_transfered_derived`,
    `status_enum`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`guarantor_id`,
    src.`account_associations_id`,
    src.`amount`,
    src.`amount_released_derived`,
    src.`amount_remaining_derived`,
    src.`amount_transfered_derived`,
    src.`status_enum`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_guarantor_funding_details AS src;
