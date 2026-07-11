SET @etl_date = CURDATE();

-- Human-reviewed semantic target: retail_banking_dm.dwd_wc_loan_balance_snapshot
DELETE FROM retail_banking_dm.dwd_wc_loan_balance_snapshot
WHERE `snapshot_date` = CAST(@etl_date AS DATE);

INSERT INTO retail_banking_dm.dwd_wc_loan_balance_snapshot (
    `id`,
    `wc_loan_id`,
    `principal_paid`,
    `realized_income_from_discount_fee`,
    `version`,
    `created_by`,
    `last_modified_by`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `overpayment_amount`,
    `principal`,
    `fee`,
    `fee_paid`,
    `penalty`,
    `penalty_paid`,
    `total_disbursement`,
    `total_discount_fee`,
    `total_discount_fee_adjustment`,
    `snapshot_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`wc_loan_id`,
    src.`principal_paid`,
    src.`realized_income_from_discount_fee`,
    src.`version`,
    src.`created_by`,
    src.`last_modified_by`,
    src.`created_on_utc`,
    src.`last_modified_on_utc`,
    src.`overpayment_amount`,
    src.`principal`,
    src.`fee`,
    src.`fee_paid`,
    src.`penalty`,
    src.`penalty_paid`,
    src.`total_disbursement`,
    src.`total_discount_fee`,
    src.`total_discount_fee_adjustment`,
    COALESCE(CAST(@etl_date AS DATE), CURDATE()) AS `snapshot_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_wc_loan_balance AS src;
