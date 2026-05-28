-- ============================================================
-- 加工作业: ADS 门店绩效评估表
-- 源表: dws_store_sales_daily, dwd_store
-- 加工逻辑: 按月汇总门店KPI -> 归一化评分 -> 填充空值
-- 写入模式: 仅刷新当月分区,按 stat_month_date 分区
-- ============================================================

SET @etl_date = COALESCE(@etl_date, CURDATE());
-- Step 1: 删除当月分区数据（保留历史月份）
DELETE FROM shop_dm.ads_store_performance
WHERE stat_month = DATE_FORMAT(@etl_date, '%Y-%m');

-- Step 2: 按月汇总门店KPI，仅处理当月
INSERT INTO shop_dm.ads_store_performance
WITH store_monthly AS (
    SELECT
        ssd.store_id,
        DATE_FORMAT(ssd.stat_date, '%Y-%m') AS stat_month,
        CONCAT(DATE_FORMAT(ssd.stat_date, '%Y-%m'), '-01') AS stat_month_date,
        MAX(s.store_name) AS store_name,
        MAX(s.city) AS city,
        MAX(s.store_type) AS store_type,
        SUM(ssd.order_count) AS total_orders,
        ROUND(SUM(ssd.total_amount), 2) AS total_amount,
        SUM(ssd.customer_count) AS customer_count,
        ROUND(SUM(ssd.payment_amount) / NULLIF(SUM(ssd.order_count), 0), 2) AS avg_order_amount
    FROM shop_dm.dws_store_sales_daily ssd
    LEFT JOIN shop_dm.dwd_store s ON ssd.store_id = s.store_id
    WHERE DATE_FORMAT(ssd.stat_date, '%Y-%m') = DATE_FORMAT(@etl_date, '%Y-%m')
    GROUP BY ssd.store_id, DATE_FORMAT(ssd.stat_date, '%Y-%m')
)
SELECT
    store_id,
    stat_month,
    stat_month_date,
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

-- Step 3: 绩效评分为空时修正为 0 (仅当月)
UPDATE shop_dm.ads_store_performance
SET performance_score = 0.00
WHERE performance_score IS NULL
  AND stat_month = DATE_FORMAT(@etl_date, '%Y-%m');

-- Step 4: 门店类型为空时设为"标准店" (仅当月)
UPDATE shop_dm.ads_store_performance
SET store_type = '标准店'
WHERE (store_type IS NULL OR store_type = '')
  AND stat_month = DATE_FORMAT(@etl_date, '%Y-%m');

-- Step 5: 客单价为空时修正为 0 (仅当月)
UPDATE shop_dm.ads_store_performance
SET avg_order_amount = 0.00
WHERE avg_order_amount IS NULL
  AND stat_month = DATE_FORMAT(@etl_date, '%Y-%m');
