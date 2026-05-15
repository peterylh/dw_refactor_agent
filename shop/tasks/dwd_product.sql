-- ============================================================
-- 加工作业: DWD 商品维度宽表
-- 源表: ods_product, ods_category
-- 加工逻辑: 关联品类维表 -> 计算毛利率 -> 清理异常值
-- ============================================================

-- Step 1: 清空目标表
TRUNCATE TABLE shop_dm.dwd_product;

-- Step 2: 关联品类表，计算毛利率
INSERT INTO shop_dm.dwd_product
SELECT
    p.product_id,
    p.product_name,
    p.category_id,
    c.category_name,
    c.parent_category_id,
    c.category_level,
    p.brand,
    p.unit,
    p.unit_price,
    p.cost_price,
    ROUND((p.unit_price - p.cost_price) / NULLIF(p.unit_price, 0) * 100, 2) AS gross_margin,
    p.spec,
    p.barcode,
    p.status,
    NOW() AS etl_time
FROM shop_dm.ods_product p
LEFT JOIN shop_dm.ods_category c ON p.category_id = c.category_id;

-- Step 3: 品类名称为空时标记为"未分类"
UPDATE shop_dm.dwd_product
SET category_name = '未分类', parent_category_id = -1, category_level = 0
WHERE category_name IS NULL;

-- Step 4: 品牌为空时使用品类名称替代
UPDATE shop_dm.dwd_product
SET brand = CONCAT('通用-', category_name)
WHERE brand IS NULL OR brand = '';
