-- ============================================================
-- 加工作业: ADS 配送绩效分析表
-- 源表: dws_daily_orders
-- 加工逻辑: 从 DWS 读取每日配送指标 -> 计算准时率 -> 修正空值
-- 说明: 复用 DWS 层日汇总，避免重复明细扫描
-- ============================================================

-- Step 1: 清空目标表
TRUNCATE TABLE olist_dm.ads_delivery_performance;

-- Step 2: 从 DWS 读取配送相关字段，计算派生指标
INSERT INTO olist_dm.ads_delivery_performance
SELECT
    stat_date,
    order_count,
    on_time_count,
    late_delivery_count AS late_count,
    ROUND(on_time_count / NULLIF(order_count, 0) * 100, 2) AS on_time_rate,
    avg_delivery_days,
    avg_delay_days,
    max_delay_days,
    NOW() AS etl_time
FROM olist_dm.dws_daily_orders;

-- Step 3: 空值修正
UPDATE olist_dm.ads_delivery_performance
SET on_time_rate = 0.00, avg_delay_days = 0.00, max_delay_days = 0
WHERE on_time_rate IS NULL;

-- Step 4: 删除无订单记录
DELETE FROM olist_dm.ads_delivery_performance
WHERE order_count = 0;
