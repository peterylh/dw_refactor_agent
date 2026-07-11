SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.bridge_group_customer_role
TRUNCATE TABLE retail_banking_dm.bridge_group_customer_role;

INSERT INTO retail_banking_dm.bridge_group_customer_role (
    `id`,
    `client_id`,
    `group_id`,
    `role_cv_id`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`client_id`,
    src.`group_id`,
    src.`role_cv_id`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_group_roles AS src;
