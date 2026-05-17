-- ============================================================
-- 加工作业: ADS 地理销售分析表
-- 源表: dwd_order_detail, dwd_customer
-- 加工逻辑: 按月+州汇总 -> 区域划分 -> 修正空值
-- ============================================================

-- Step 1: 清空目标表
TRUNCATE TABLE olist_dm.ads_geographic_sales;

-- Step 2: 按月地理汇总
INSERT INTO olist_dm.ads_geographic_sales
SELECT
    dod.order_month AS stat_month,
    COALESCE(dc.customer_state, 'ZZ') AS customer_state,
    COALESCE(dc.customer_region, 'Desconhecido') AS customer_region,
    COUNT(DISTINCT dod.order_id) AS order_count,
    COUNT(DISTINCT dod.customer_id) AS customer_count,
    ROUND(SUM(dod.price + dod.freight_value), 2) AS total_revenue,
    ROUND(AVG(dod.freight_value), 2) AS avg_freight,
    NOW() AS etl_time
FROM olist_dm.dwd_order_detail dod
LEFT JOIN olist_dm.dwd_customer dc ON dod.customer_id = dc.customer_id
GROUP BY dod.order_month, dc.customer_state, dc.customer_region;

-- Step 3: 删除无收入记录
DELETE FROM olist_dm.ads_geographic_sales
WHERE total_revenue = 0;
