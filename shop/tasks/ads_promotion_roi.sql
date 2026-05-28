-- ============================================================
-- 加工作业: ADS 促销投资回报分析表
-- 源表: dws_promotion_effect_daily, dwd_promotion
-- 加工逻辑: 计算折扣成本 -> 计算ROI -> 填充默认值
-- 写入模式: 按 stat_date 分区, DELETE + INSERT 按日处理
-- ============================================================

SET @etl_date = COALESCE(@etl_date, CURDATE());
DELETE FROM shop_dm.ads_promotion_roi WHERE stat_date = CAST(@etl_date AS DATE);

INSERT INTO shop_dm.ads_promotion_roi
SELECT
    pe.promotion_id,
    pe.stat_date,
    pe.promotion_name,
    pe.promotion_type,
    pe.order_count AS total_orders,
    pe.sale_amount AS total_sale_amount,
    pe.discount_amount AS total_discount_cost,
    CASE
        WHEN pe.sale_amount > 0 THEN ROUND(pe.discount_amount / pe.sale_amount * 100, 2)
        ELSE NULL
    END AS avg_discount_rate,
    CASE
        WHEN pe.discount_amount > 0 THEN ROUND(pe.sale_amount / pe.discount_amount, 2)
        ELSE NULL
    END AS roi,
    NOW() AS etl_time
FROM shop_dm.dws_promotion_effect_daily pe
WHERE pe.stat_date = CAST(@etl_date AS DATE);

UPDATE shop_dm.ads_promotion_roi
SET promotion_name = CONCAT('促销活动-', promotion_id)
WHERE (promotion_name IS NULL OR promotion_name = '')
  AND stat_date = CAST(@etl_date AS DATE);

UPDATE shop_dm.ads_promotion_roi
SET total_discount_cost = 0.00
WHERE total_discount_cost IS NULL
  AND stat_date = CAST(@etl_date AS DATE);
