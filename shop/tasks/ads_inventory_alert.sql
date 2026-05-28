-- ============================================================
-- 加工作业: ADS 库存预警分析表
-- 源表: dws_inventory_daily, dwd_product, dwd_store, dws_product_sales_daily
-- 加工逻辑: 关联维度 -> 计算日均销售速度 -> 预估库存支撑天数 -> 预警分级
-- 写入模式: 按 stat_date 分区, DELETE + INSERT 按日处理
-- ============================================================

SET @etl_date = COALESCE(@etl_date, CURDATE());
DELETE FROM shop_dm.ads_inventory_alert WHERE stat_date = CAST(@etl_date AS DATE);

INSERT INTO shop_dm.ads_inventory_alert
WITH sales_velocity AS (
    SELECT
        product_id,
        ROUND(AVG(sale_quantity), 2) AS daily_sales_velocity
    FROM shop_dm.dws_product_sales_daily
    WHERE stat_date BETWEEN DATE_SUB(CAST(@etl_date AS DATE), INTERVAL 7 DAY)
      AND CAST(@etl_date AS DATE)
    GROUP BY product_id
)
SELECT
    inv.product_id,
    inv.store_id,
    inv.stat_date,
    MAX(p.product_name) AS product_name,
    MAX(s.store_name) AS store_name,
    inv.quantity,
    inv.safety_stock,
    inv.stock_status,
    inv.days_since_restock,
    sv.daily_sales_velocity,
    CASE
        WHEN sv.daily_sales_velocity > 0 AND inv.quantity > 0
            THEN ROUND(inv.quantity / sv.daily_sales_velocity, 1)
        WHEN sv.daily_sales_velocity IS NULL OR sv.daily_sales_velocity = 0
            THEN NULL
        ELSE 0
    END AS days_of_stock_remaining,
    CASE
        WHEN inv.quantity <= 0 THEN '严重'
        WHEN inv.quantity <= inv.safety_stock * 0.5 THEN '预警'
        WHEN inv.quantity <= inv.safety_stock THEN '关注'
        ELSE '正常'
    END AS alert_level,
    NOW() AS etl_time
FROM shop_dm.dws_inventory_daily inv
LEFT JOIN shop_dm.dwd_product p
    ON inv.product_id = p.product_id
    AND p.snapshot_date = CAST(@etl_date AS DATE)
LEFT JOIN shop_dm.dwd_store s
    ON inv.store_id = s.store_id
    AND s.snapshot_date = CAST(@etl_date AS DATE)
LEFT JOIN sales_velocity sv
    ON inv.product_id = sv.product_id
WHERE inv.stat_date = CAST(@etl_date AS DATE)
GROUP BY inv.product_id, inv.store_id, inv.stat_date,
    inv.quantity, inv.safety_stock, inv.stock_status,
    inv.days_since_restock, sv.daily_sales_velocity;

UPDATE shop_dm.ads_inventory_alert
SET product_name = CONCAT('商品-', product_id)
WHERE (product_name IS NULL OR product_name = '')
  AND stat_date = CAST(@etl_date AS DATE);

UPDATE shop_dm.ads_inventory_alert
SET store_name = CONCAT('门店-', store_id)
WHERE (store_name IS NULL OR store_name = '')
  AND stat_date = CAST(@etl_date AS DATE);
