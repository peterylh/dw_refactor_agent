SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.bridge_customer_address
TRUNCATE TABLE retail_banking_dm.bridge_customer_address;

INSERT INTO retail_banking_dm.bridge_customer_address (
    `id`,
    `client_id`,
    `address_id`,
    `address_type_id`,
    `is_active`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`client_id`,
    src.`address_id`,
    src.`address_type_id`,
    src.`is_active`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_client_address AS src;
