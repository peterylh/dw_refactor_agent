-- ============================================================
-- 加工作业: DWS 品类月度销售汇总
-- 源表: dwd_order_detail
-- 加工逻辑: 按月+品类汇总 -> 修正空值
-- ============================================================

-- Step 1: 清空目标表
TRUNCATE TABLE olist_dm.dws_product_category_monthly;

-- Step 2: 按月品类汇总
INSERT INTO olist_dm.dws_product_category_monthly
SELECT
    product_category_name_english,
    order_month AS stat_month,
    COUNT(DISTINCT order_id) AS order_count,
    COUNT(DISTINCT order_item_id) AS item_count,
    ROUND(SUM(price + freight_value), 2) AS total_revenue,
    ROUND(AVG(price), 2) AS avg_price,
    ROUND(AVG(freight_value), 2) AS avg_freight,
    ROUND(AVG(review_score), 2) AS avg_review_score,
    NOW() AS etl_time
FROM olist_dm.dwd_order_detail
GROUP BY product_category_name_english, order_month;

-- Step 3: 评分空值默认 3
UPDATE olist_dm.dws_product_category_monthly
SET avg_review_score = 3.00
WHERE avg_review_score IS NULL;

-- Step 4: 删除无收入记录
DELETE FROM olist_dm.dws_product_category_monthly
WHERE total_revenue = 0;
