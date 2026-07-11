SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_share_market_price
TRUNCATE TABLE retail_banking_dm.dwd_share_market_price;

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
FROM retail_banking_dm.ods_fineract_m_share_product_market_price AS src;
