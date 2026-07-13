-- Human-reviewed semantic target: retail_banking_dm.dim_rate
TRUNCATE TABLE retail_banking_dm.dim_rate;

INSERT INTO retail_banking_dm.dim_rate (
    `id`,
    `name`,
    `percentage`,
    `active`,
    `product_apply`,
    `created_date`,
    `createdby_id`,
    `lastmodifiedby_id`,
    `lastmodified_date`,
    `approve_user`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`name`,
    src.`percentage`,
    src.`active`,
    src.`product_apply`,
    src.`created_date`,
    src.`createdby_id`,
    src.`lastmodifiedby_id`,
    src.`lastmodified_date`,
    src.`approve_user`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_rate AS src;
