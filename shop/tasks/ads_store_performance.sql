-- ============================================================
-- 加工作业: ADS 门店绩效评估表
-- 源表: dws_store_sales_daily, dwd_store
-- 加工逻辑: 按月汇总门店KPI -> 归一化评分 -> 填充空值
-- ============================================================

-- Step 1: 清空目标表
TRUNCATE TABLE shop_dm.ads_store_performance;

-- Step 2: 按月汇总门店KPI，窗口函数计算同月最大值归一化评分
INSERT INTO shop_dm.ads_store_performance
WITH store_monthly AS (
    SELECT
        ssd.store_id,
        DATE_FORMAT(ssd.stat_date, '%Y-%m') AS stat_month,
        MAX(s.store_name) AS store_name,
        MAX(s.city) AS city,
        MAX(s.store_type) AS store_type,
        SUM(ssd.order_count) AS total_orders,
        ROUND(SUM(ssd.total_amount), 2) AS total_amount,
        SUM(ssd.customer_count) AS customer_count,
        ROUND(SUM(ssd.payment_amount) / NULLIF(SUM(ssd.order_count), 0), 2) AS avg_order_amount
    FROM shop_dm.dws_store_sales_daily ssd
    LEFT JOIN shop_dm.dwd_store s ON ssd.store_id = s.store_id
    GROUP BY ssd.store_id, DATE_FORMAT(ssd.stat_date, '%Y-%m')
)
SELECT
    store_id,
    stat_month,
    store_name,
    city,
    store_type,
    total_orders,
    total_amount,
    customer_count,
    avg_order_amount,
    ROUND(
        total_orders / NULLIF(MAX(total_orders) OVER (PARTITION BY stat_month), 0) * 30 +
        total_amount / NULLIF(MAX(total_amount) OVER (PARTITION BY stat_month), 0) * 40 +
        customer_count / NULLIF(MAX(customer_count) OVER (PARTITION BY stat_month), 0) * 30, 2
    ) AS performance_score,
    NOW() AS etl_time
FROM store_monthly;

-- Step 3: 绩效评分为空时修正为 0
UPDATE shop_dm.ads_store_performance
SET performance_score = 0.00
WHERE performance_score IS NULL;

-- Step 4: 门店类型为空时设为"标准店"
UPDATE shop_dm.ads_store_performance
SET store_type = '标准店'
WHERE store_type IS NULL OR store_type = '';

-- Step 5: 客单价为空时修正为 0
UPDATE shop_dm.ads_store_performance
SET avg_order_amount = 0.00
WHERE avg_order_amount IS NULL;
