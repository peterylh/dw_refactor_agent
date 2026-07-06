-- ============================================================
-- 加工作业: DWS 促销效果日汇总表
-- 源表: dwd_order_detail, dim_promotion
-- 加工逻辑: 按促销+日期汇总 -> 关联促销维度 -> 清理异常数据
-- 写入模式: 按 stat_date 分区, DELETE + INSERT 按日处理
-- ============================================================

SET @etl_date = COALESCE(@etl_date, CURDATE());
DELETE FROM shop_layering_fix_dm.dws_promotion_effect_daily WHERE IF(@full_refresh = 1, 1=1, stat_date = CAST(@etl_date AS DATE));

INSERT INTO shop_layering_fix_dm.dws_promotion_effect_daily
SELECT
    od.promotion_id,
    od.order_date AS stat_date,
    MAX(p.promotion_name) AS promotion_name,
    MAX(p.promotion_type) AS promotion_type,
    COUNT(DISTINCT od.order_id) AS order_count,
    COUNT(DISTINCT od.customer_id) AS customer_count,
    SUM(od.quantity) AS sale_quantity,
    SUM(od.subtotal) AS sale_amount,
    SUM(od.discount) AS discount_amount,
    NOW() AS etl_time
FROM shop_layering_fix_dm.dwd_order_detail od
LEFT JOIN shop_layering_fix_dm.dim_promotion p
    ON od.promotion_id = p.promotion_id
    AND p.snapshot_date = IF(@full_refresh = 1, DATE(od.order_date), CAST(@etl_date AS DATE))
WHERE IF(@full_refresh = 1, 1=1, od.order_date = CAST(@etl_date AS DATE))
  AND od.promotion_id IS NOT NULL
GROUP BY od.promotion_id, od.order_date;

UPDATE shop_layering_fix_dm.dws_promotion_effect_daily
SET discount_amount = 0.00
WHERE discount_amount IS NULL
  AND IF(@full_refresh = 1, 1=1, stat_date = CAST(@etl_date AS DATE));

UPDATE shop_layering_fix_dm.dws_promotion_effect_daily
SET promotion_name = CONCAT('促销活动-', promotion_id)
WHERE (promotion_name IS NULL OR promotion_name = '')
  AND IF(@full_refresh = 1, 1=1, stat_date = CAST(@etl_date AS DATE));

DELETE FROM shop_layering_fix_dm.dws_promotion_effect_daily
WHERE sale_amount < 0
  AND IF(@full_refresh = 1, 1=1, stat_date = CAST(@etl_date AS DATE));
