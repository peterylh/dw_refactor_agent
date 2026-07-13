SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_share_market_price
DELETE FROM retail_banking_dm.dwd_share_market_price
WHERE `business_date` = CAST(@etl_date AS DATE);
DELETE FROM retail_banking_dm.dwd_share_market_price
WHERE `business_date` IS NULL;

INSERT INTO retail_banking_dm.dwd_share_market_price (
    `id`,
    `product_id`,
    `from_date`,
    `share_value`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`product_id`,
    src.`from_date`,
    src.`share_value`,
    DATE(src.`from_date`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_share_product_market_price AS src
WHERE DATE(src.`from_date`) = CAST(@etl_date AS DATE)
   OR DATE(src.`from_date`) IS NULL;
