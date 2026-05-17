-- ============================================================
-- 加工作业: ADS 品类月度趋势分析表
-- 源表: dws_product_category_monthly
-- 加工逻辑: 复用 DWS 月度汇总 -> 窗口函数计算环比增长率 -> 修正空值
-- ============================================================

-- Step 1: 清空目标表
TRUNCATE TABLE olist_dm.ads_category_monthly_trend;

-- Step 2: 从 DWS 读取品类月度数据，LAG 计算环比
INSERT INTO olist_dm.ads_category_monthly_trend
SELECT
    product_category_name_english,
    stat_month,
    order_count,
    item_count,
    total_revenue,
    avg_price,
    avg_review_score,
    ROUND((total_revenue - LAG(total_revenue, 1)
        OVER (PARTITION BY product_category_name_english ORDER BY stat_month))
        / NULLIF(LAG(total_revenue, 1)
            OVER (PARTITION BY product_category_name_english ORDER BY stat_month), 0) * 100, 2)
    AS revenue_growth_rate,
    NOW() AS etl_time
FROM olist_dm.dws_product_category_monthly;

-- Step 3: 环比增长率为空时设为 0(首月无上期数据)
UPDATE olist_dm.ads_category_monthly_trend
SET revenue_growth_rate = 0.00
WHERE revenue_growth_rate IS NULL;

-- Step 4: 评分为空默认 3
UPDATE olist_dm.ads_category_monthly_trend
SET avg_review_score = 3.00
WHERE avg_review_score IS NULL;

-- Step 5: 删除无收入记录
DELETE FROM olist_dm.ads_category_monthly_trend
WHERE total_revenue = 0;
