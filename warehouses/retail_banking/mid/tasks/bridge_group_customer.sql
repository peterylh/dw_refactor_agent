-- Human-reviewed semantic target: retail_banking_dm.bridge_group_customer
TRUNCATE TABLE retail_banking_dm.bridge_group_customer;

INSERT INTO retail_banking_dm.bridge_group_customer (
    `group_id`,
    `client_id`,
    `etl_time`
)
SELECT
    src.`group_id`,
    src.`client_id`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_group_client AS src;
