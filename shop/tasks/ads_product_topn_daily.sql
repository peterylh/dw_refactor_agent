-- ============================================================
-- 加工作业: ADS 商品日销售排行表
-- 源表: dws_product_sales_daily, dwd_product
-- 加工逻辑: 每日排名 -> 关联商品维表 -> 剔除超出TOP10的数据
-- 写入模式: 按 stat_date 分区, DELETE + INSERT 按日处理
-- ============================================================

SET @etl_date = COALESCE(@etl_date, CURDATE());
-- Step 1: 删除当前统计日期的数据
DELETE FROM shop_dm.ads_product_topn_daily WHERE stat_date = CAST(@etl_date AS DATE);

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
WHERE psd.sale_amount > 0
  AND psd.stat_date = CAST(@etl_date AS DATE);

-- Step 3: 品类名称为空时设为"未分类"
UPDATE shop_dm.ads_product_topn_daily
SET category_name = '未分类'
WHERE category_name IS NULL
  AND stat_date = CAST(@etl_date AS DATE);

-- Step 4: 商品名称为空时用 ID 填充
UPDATE shop_dm.ads_product_topn_daily
SET product_name = CONCAT('商品#', CAST(product_id AS STRING))
WHERE product_name IS NULL
  AND stat_date = CAST(@etl_date AS DATE);

-- Step 5: 只保留每日 TOP 10
DELETE FROM shop_dm.ads_product_topn_daily
WHERE rank_num > 10
  AND stat_date = CAST(@etl_date AS DATE);
