-- ============================================================
-- 加工作业: ADS 商品日销售排行表
-- 源表: dws_product_sales_daily, dwd_product
-- 加工逻辑: 每日排名 -> 关联商品维表 -> 剔除超出TOP10的数据
-- ============================================================

-- Step 1: 清空目标表
TRUNCATE TABLE shop_dm.ads_product_topn_daily;

-- Step 2: 每日商品销售排名(窗口函数)，关联商品维表
INSERT INTO shop_dm.ads_product_topn_daily
SELECT
    psd.stat_date,
    psd.product_id,
    p.product_name,
    p.category_name,
    psd.sale_quantity,
    psd.sale_amount,
    RANK() OVER (PARTITION BY psd.stat_date ORDER BY psd.sale_amount DESC) AS rank_num,
    NOW() AS etl_time
FROM shop_dm.dws_product_sales_daily psd
LEFT JOIN shop_dm.dwd_product p ON psd.product_id = p.product_id
WHERE psd.sale_amount > 0;

-- Step 3: 品类名称为空时设为"未分类"
UPDATE shop_dm.ads_product_topn_daily
SET category_name = '未分类'
WHERE category_name IS NULL;

-- Step 4: 商品名称为空时用 ID 填充
UPDATE shop_dm.ads_product_topn_daily
SET product_name = CONCAT('商品#', CAST(product_id AS STRING))
WHERE product_name IS NULL;

-- Step 5: 只保留每日 TOP 10
DELETE FROM shop_dm.ads_product_topn_daily
WHERE rank_num > 10;
