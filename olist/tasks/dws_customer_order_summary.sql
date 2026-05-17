-- ============================================================
-- 加工作业: DWS 客户订单汇总表
-- 源表: dwd_order_detail
-- 加工逻辑: 按客户+日期汇总 -> 修正空值 -> 删除异常
-- ============================================================

-- Step 1: 清空目标表
TRUNCATE TABLE olist_dm.dws_customer_order_summary;

-- Step 2: 按客户+下单日期汇总
INSERT INTO olist_dm.dws_customer_order_summary
SELECT
    customer_id,
    DATE(order_purchase_timestamp) AS stat_date,
    COUNT(DISTINCT order_id) AS order_count,
    ROUND(SUM(price), 2) AS total_price,
    ROUND(SUM(freight_value), 2) AS total_freight,
    ROUND(SUM(price + freight_value), 2) AS total_revenue,
    ROUND(SUM(price + freight_value) / NULLIF(COUNT(DISTINCT order_id), 0), 2) AS avg_order_value,
    NOW() AS etl_time
FROM olist_dm.dwd_order_detail
GROUP BY customer_id, DATE(order_purchase_timestamp);

-- Step 3: 平均订单价值为空修正
UPDATE olist_dm.dws_customer_order_summary
SET avg_order_value = 0.00
WHERE avg_order_value IS NULL;

-- Step 4: 删除实付为 0 的记录
DELETE FROM olist_dm.dws_customer_order_summary
WHERE total_revenue = 0;
