SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_customer_transfer_event
TRUNCATE TABLE retail_banking_dm.dwd_customer_transfer_event;

INSERT INTO retail_banking_dm.dwd_customer_transfer_event (
    `id`,
    `client_id`,
    `from_office_id`,
    `to_office_id`,
    `proposed_transfer_date`,
    `transfer_type`,
    `submitted_on`,
    `submitted_by`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`client_id`,
    src.`from_office_id`,
    src.`to_office_id`,
    src.`proposed_transfer_date`,
    src.`transfer_type`,
    src.`submitted_on`,
    src.`submitted_by`,
    DATE(src.`proposed_transfer_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_client_transfer_details AS src;
