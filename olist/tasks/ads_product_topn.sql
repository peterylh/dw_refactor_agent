-- ============================================================
-- 加工作业: ADS 商品销售排行表
-- 源表: dwd_order_detail, dwd_product
-- 加工逻辑: 按日排名 -> 关联品类 -> 截取 Top N
-- ============================================================

-- Step 1: 清空目标表
TRUNCATE TABLE olist_dm.ads_product_topn;

-- Step 2: 商品日销售排名
INSERT INTO olist_dm.ads_product_topn
SELECT
    DATE(dod.order_purchase_timestamp) AS stat_date,
    dod.product_id,
    dp.product_category_name_english,
    COUNT(DISTINCT dod.order_item_id) AS item_count,
    ROUND(SUM(dod.price + dod.freight_value), 2) AS total_revenue,
    ROUND(AVG(dod.price), 2) AS avg_price,
    RANK() OVER (
        PARTITION BY DATE(dod.order_purchase_timestamp)
        ORDER BY SUM(dod.price + dod.freight_value) DESC
    ) AS rank_num,
    NOW() AS etl_time
FROM olist_dm.dwd_order_detail dod
LEFT JOIN olist_dm.dwd_product dp ON dod.product_id = dp.product_id
GROUP BY DATE(dod.order_purchase_timestamp), dod.product_id, dp.product_category_name_english;

-- Step 3: 品类名空值填充
UPDATE olist_dm.ads_product_topn
SET product_category_name_english = 'unknown'
WHERE product_category_name_english IS NULL;

-- Step 4: 只保留 Top 20
DELETE FROM olist_dm.ads_product_topn
WHERE rank_num > 20;
