SET @etl_end_date = COALESCE(@etl_end_date, CURDATE());
SET @etl_start_date = COALESCE(@etl_start_date, @etl_end_date);

-- Human-reviewed semantic target: retail_banking_dm.dwd_wc_breach_event
TRUNCATE TABLE retail_banking_dm.dwd_wc_breach_event;

INSERT INTO retail_banking_dm.dwd_wc_breach_event (
    `id`,
    `wc_loan_id`,
    `action`,
    `start_date`,
    `end_date`,
    `created_by`,
    `last_modified_by`,
    `created_on_utc`,
    `last_modified_on_utc`,
    `minimum_payment`,
    `minimum_payment_type`,
    `frequency`,
    `frequency_type`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`wc_loan_id`,
    src.`action`,
    src.`start_date`,
    src.`end_date`,
    src.`created_by`,
    src.`last_modified_by`,
    src.`created_on_utc`,
    src.`last_modified_on_utc`,
    src.`minimum_payment`,
    src.`minimum_payment_type`,
    src.`frequency`,
    src.`frequency_type`,
    DATE(src.`start_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_wc_loan_breach_action AS src
WHERE (DATE(src.`start_date`) IS NULL OR (DATE(src.`start_date`) >= CAST(@etl_start_date AS DATE) AND DATE(src.`start_date`) <= CAST(@etl_end_date AS DATE)));
