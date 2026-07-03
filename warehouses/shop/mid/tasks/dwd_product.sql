-- ============================================================
-- 加工作业: DWD 商品维度宽表 (每日快照)
-- 源表: ods_product, ods_category
-- 加工逻辑: 关联品类维表 -> 计算毛利率 -> 清理异常值
-- 写入模式: 追加每日快照,按 snapshot_date 分区
-- ============================================================

SET @etl_date = COALESCE(@etl_date, CURDATE());
-- Step 1: 关联品类表，计算毛利率，回填合并
INSERT INTO shop_dm.dwd_product
SELECT
    p.product_id,
    CAST(@etl_date AS DATE) AS snapshot_date,
    NOW() AS etl_time,
    p.product_name,
    p.category_id,
    COALESCE(c.category_name, '未分类') AS category_name,
    COALESCE(c.parent_category_id, -1) AS parent_category_id,
    COALESCE(c.category_level, 0) AS category_level,
    COALESCE(NULLIF(p.brand, ''), CONCAT('通用-', COALESCE(c.category_name, '未分类'))) AS brand,
    p.unit,
    p.unit_price,
    p.cost_price,
    ROUND((p.unit_price - p.cost_price) / NULLIF(p.unit_price, 0) * 100, 2) AS gross_margin,
    p.spec,
    p.barcode,
    p.status
FROM (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY product_id ORDER BY load_time DESC) AS rn
    FROM shop_dm.ods_product
    WHERE DATE(load_time) <= CAST(@etl_date AS DATE)
) p
LEFT JOIN shop_dm.ods_category c ON p.category_id = c.category_id
WHERE p.rn = 1;
