SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dim_address
TRUNCATE TABLE retail_banking_dm.dim_address;

INSERT INTO retail_banking_dm.dim_address (
    `id`,
    `street`,
    `address_line_1`,
    `address_line_2`,
    `address_line_3`,
    `town_village`,
    `city`,
    `county_district`,
    `state_province_id`,
    `country_id`,
    `postal_code`,
    `latitude`,
    `longitude`,
    `created_by`,
    `created_on`,
    `updated_by`,
    `updated_on`,
    `etl_time`
)
SELECT
    src.`id`,
    CASE WHEN src.`street` IS NULL THEN NULL ELSE '***' END AS `street`,
    CASE WHEN src.`address_line_1` IS NULL THEN NULL ELSE '***' END AS `address_line_1`,
    CASE WHEN src.`address_line_2` IS NULL THEN NULL ELSE '***' END AS `address_line_2`,
    CASE WHEN src.`address_line_3` IS NULL THEN NULL ELSE '***' END AS `address_line_3`,
    CASE WHEN src.`town_village` IS NULL THEN NULL ELSE '***' END AS `town_village`,
    CASE WHEN src.`city` IS NULL THEN NULL ELSE '***' END AS `city`,
    CASE WHEN src.`county_district` IS NULL THEN NULL ELSE '***' END AS `county_district`,
    src.`state_province_id`,
    src.`country_id`,
    CASE WHEN src.`postal_code` IS NULL THEN NULL ELSE '***' END AS `postal_code`,
    CASE WHEN src.`latitude` IS NULL THEN NULL ELSE '***' END AS `latitude`,
    CASE WHEN src.`longitude` IS NULL THEN NULL ELSE '***' END AS `longitude`,
    src.`created_by`,
    src.`created_on`,
    src.`updated_by`,
    src.`updated_on`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_address AS src;
