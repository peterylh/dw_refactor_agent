-- ============================================================
-- 加工作业: DWD 商品维度宽表 (批量全量刷新)
-- 源表: ods_product, ods_category
-- 加工逻辑: 按 product_id + DATE(load_time) 生成所有日快照
-- 写入模式: 一次 INSERT 全部历史快照
-- ============================================================

INSERT INTO shop_dm.dwd_product
SELECT
    p.product_id,
    DATE(p.load_time) AS snapshot_date,
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
        ROW_NUMBER() OVER (PARTITION BY product_id, DATE(load_time) ORDER BY load_time DESC) AS rn
    FROM shop_dm.ods_product
) p
LEFT JOIN shop_dm.ods_category c ON p.category_id = c.category_id
WHERE p.rn = 1;
