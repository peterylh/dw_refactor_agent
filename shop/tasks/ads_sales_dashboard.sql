-- ============================================================
-- 加工作业: ADS 销售驾驶舱汇总表
-- 源表: dwd_order_detail（直接从 DWD 聚合，跳过 DWS 层）
-- 原因: 驾驶舱需要全店级日聚合 + 环比计算，DWS 按门店维度汇总无法直接复用
-- 加工逻辑: 全店日汇总 -> 计算环比增长率 -> 填充空值
-- 写入模式: 全量刷新,按 stat_date 分区
-- ============================================================

-- Step 1: 清空目标表
TRUNCATE TABLE shop_dm.ads_sales_dashboard;

-- Step 2: 日度全店汇总 + LAG 计算环比增长率(从 DWD 层直接计算避免跨店客户重复)
INSERT INTO shop_dm.ads_sales_dashboard
WITH daily_base AS (
    SELECT
        order_date AS stat_date,
        COUNT(DISTINCT order_id) AS total_orders,
        COUNT(DISTINCT customer_id) AS total_customers,
        ROUND(SUM(subtotal), 2) AS total_amount,
        ROUND(SUM(discount), 2) AS total_discount,
        ROUND(SUM(subtotal - discount) / NULLIF(COUNT(DISTINCT order_id), 0), 2) AS avg_order_amount
    FROM shop_dm.dwd_order_detail
    GROUP BY order_date
)
SELECT
    stat_date,
    total_orders,
    total_customers,
    total_amount,
    total_discount,
    avg_order_amount,
    ROUND((total_orders - LAG(total_orders, 1) OVER (ORDER BY stat_date))
        / NULLIF(LAG(total_orders, 1) OVER (ORDER BY stat_date), 0) * 100, 2) AS order_growth_rate,
    ROUND((total_amount - LAG(total_amount, 1) OVER (ORDER BY stat_date))
        / NULLIF(LAG(total_amount, 1) OVER (ORDER BY stat_date), 0) * 100, 2) AS amount_growth_rate,
    NOW() AS etl_time
FROM daily_base;

-- Step 3: 订单增长率为空(首日无环比)时设为 0
UPDATE shop_dm.ads_sales_dashboard
SET order_growth_rate = 0.00
WHERE order_growth_rate IS NULL;

-- Step 4: 金额增长率为空时设为 0
UPDATE shop_dm.ads_sales_dashboard
SET amount_growth_rate = 0.00
WHERE amount_growth_rate IS NULL;
