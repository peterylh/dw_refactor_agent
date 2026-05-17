-- ============================================================
-- 加工作业: DWD 商品明细维表
-- 源表: ods_product, ods_category_translation
-- 加工逻辑: 品类翻译 -> 体积计算 -> 重量分级 -> 修正列名
-- ============================================================

-- Step 1: 清空目标表
TRUNCATE TABLE olist_dm.dwd_product;

-- Step 2: 关联翻译表，计算体积与重量等级，修正列名拼写
INSERT INTO olist_dm.dwd_product
SELECT
    p.product_id,
    p.product_category_name,
    ct.product_category_name_english,
    p.product_name_lenght AS product_name_length,
    p.product_description_lenght AS product_description_length,
    p.product_photos_qty,
    p.product_weight_g,
    p.product_length_cm,
    p.product_height_cm,
    p.product_width_cm,
    ROUND(p.product_length_cm * p.product_height_cm * p.product_width_cm, 2) AS product_volume_cm3,
    CASE
        WHEN p.product_weight_g IS NULL THEN 'unknown'
        WHEN p.product_weight_g < 200 THEN '轻'
        WHEN p.product_weight_g < 1000 THEN '中'
        WHEN p.product_weight_g < 5000 THEN '重'
        ELSE '超重'
    END AS product_weight_class,
    NOW() AS etl_time
FROM olist_dm.ods_product p
LEFT JOIN olist_dm.ods_category_translation ct ON p.product_category_name = ct.product_category_name;

-- Step 3: 品类名为空标记
UPDATE olist_dm.dwd_product
SET product_category_name = 'unknown', product_category_name_english = 'unknown'
WHERE product_category_name IS NULL;

-- Step 4: 重量等级为空标记
UPDATE olist_dm.dwd_product
SET product_weight_class = 'unknown'
WHERE product_weight_class IS NULL;
