-- ============================================================
-- 加工作业: DWS 日订单汇总表
-- 源表: dwd_order_detail
-- 加工逻辑: 按日汇总订单 -> 配送指标 -> 修正空值
-- ============================================================

-- Step 1: 清空目标表
TRUNCATE TABLE olist_dm.dws_daily_orders;

-- Step 2: 按日汇总(含配送指标)
INSERT INTO olist_dm.dws_daily_orders
SELECT
    DATE(order_purchase_timestamp) AS stat_date,
    COUNT(DISTINCT order_id) AS order_count,
    COUNT(DISTINCT customer_id) AS customer_count,
    COUNT(DISTINCT order_item_id) AS item_count,
    ROUND(SUM(price + freight_value), 2) AS total_revenue,
    ROUND(SUM(freight_value), 2) AS total_freight,
    ROUND(SUM(price + freight_value) / NULLIF(COUNT(DISTINCT order_id), 0), 2) AS avg_order_value,
    SUM(CASE WHEN delivery_delay_days > 0 THEN 1 ELSE 0 END) AS late_delivery_count,
    SUM(CASE WHEN delivery_delay_days = 0 THEN 1 ELSE 0 END) AS on_time_count,
    ROUND(AVG(delivery_days), 2) AS avg_delivery_days,
    ROUND(AVG(CASE WHEN delivery_delay_days > 0 THEN delivery_delay_days ELSE NULL END), 2) AS avg_delay_days,
    MAX(delivery_delay_days) AS max_delay_days,
    NOW() AS etl_time
FROM olist_dm.dwd_order_detail
GROUP BY DATE(order_purchase_timestamp);

-- Step 3: 空值修正
UPDATE olist_dm.dws_daily_orders
SET avg_order_value = 0.00
WHERE avg_order_value IS NULL;

UPDATE olist_dm.dws_daily_orders
SET avg_delay_days = 0.00, max_delay_days = 0
WHERE avg_delay_days IS NULL;

-- Step 4: 删除无订单记录
DELETE FROM olist_dm.dws_daily_orders
WHERE order_count = 0;
