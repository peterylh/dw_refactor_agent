SET @etl_date = CURDATE();

-- Human-reviewed semantic target: retail_banking_dm.dwd_loan_arrears_snapshot
DELETE FROM retail_banking_dm.dwd_loan_arrears_snapshot
WHERE `snapshot_date` = CAST(@etl_date AS DATE);

INSERT INTO retail_banking_dm.dwd_loan_arrears_snapshot (
    `loan_id`,
    `principal_overdue_derived`,
    `interest_overdue_derived`,
    `fee_charges_overdue_derived`,
    `penalty_charges_overdue_derived`,
    `total_overdue_derived`,
    `overdue_since_date_derived`,
    `snapshot_date`,
    `etl_time`
)
SELECT
    src.`loan_id`,
    src.`principal_overdue_derived`,
    src.`interest_overdue_derived`,
    src.`fee_charges_overdue_derived`,
    src.`penalty_charges_overdue_derived`,
    src.`total_overdue_derived`,
    src.`overdue_since_date_derived`,
    COALESCE(CAST(@etl_date AS DATE), CURDATE()) AS `snapshot_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_loan_arrears_aging AS src;
