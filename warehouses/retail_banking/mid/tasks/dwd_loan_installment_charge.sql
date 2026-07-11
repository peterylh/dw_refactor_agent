SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_loan_installment_charge
TRUNCATE TABLE retail_banking_dm.dwd_loan_installment_charge;

INSERT INTO retail_banking_dm.dwd_loan_installment_charge (
    `id`,
    `loan_charge_id`,
    `loan_schedule_id`,
    `due_date`,
    `amount`,
    `amount_paid_derived`,
    `amount_waived_derived`,
    `amount_writtenoff_derived`,
    `amount_outstanding_derived`,
    `is_paid_derived`,
    `waived`,
    `amount_through_charge_payment`,
    `loan_id`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`loan_charge_id`,
    src.`loan_schedule_id`,
    src.`due_date`,
    src.`amount`,
    src.`amount_paid_derived`,
    src.`amount_waived_derived`,
    src.`amount_writtenoff_derived`,
    src.`amount_outstanding_derived`,
    src.`is_paid_derived`,
    src.`waived`,
    src.`amount_through_charge_payment`,
    enrichment_parent.`loan_id` AS `loan_id`,
    DATE(src.`due_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_loan_installment_charge AS src
LEFT JOIN retail_banking_dm.ods_fineract_m_loan_charge AS enrichment_parent
    ON src.`loan_charge_id` = enrichment_parent.`id`;
