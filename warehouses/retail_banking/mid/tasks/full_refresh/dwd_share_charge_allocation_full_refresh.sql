SET @etl_end_date = COALESCE(@etl_end_date, CURDATE());
SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date);

-- Human-reviewed semantic target: retail_banking_dm.dwd_share_charge_allocation
TRUNCATE TABLE retail_banking_dm.dwd_share_charge_allocation;

INSERT INTO retail_banking_dm.dwd_share_charge_allocation (
    `id`,
    `share_transaction_id`,
    `charge_transaction_id`,
    `amount`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`share_transaction_id`,
    src.`charge_transaction_id`,
    src.`amount`,
    DATE(date_parent.`transaction_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_share_account_charge_paid_by AS src
LEFT JOIN retail_banking_dm.ods_fineract_m_share_account_transactions AS date_parent
    ON src.`share_transaction_id` = date_parent.`id`
WHERE (DATE(date_parent.`transaction_date`) IS NULL OR (DATE(date_parent.`transaction_date`) >= CAST(@etl_start_date AS DATE) AND DATE(date_parent.`transaction_date`) <= CAST(@etl_end_date AS DATE)));
