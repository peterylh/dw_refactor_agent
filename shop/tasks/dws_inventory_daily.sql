-- ============================================================
-- 加工作业: DWS 库存日汇总表
-- 源表: dwd_inventory
-- 加工逻辑: 按商品+门店+日期汇总库存指标
-- 写入模式: 按 stat_date 分区, DELETE + INSERT 按日处理
-- ============================================================

SET @etl_date = COALESCE(@etl_date, CURDATE());
DELETE FROM shop_dm.dws_inventory_daily WHERE stat_date = CAST(@etl_date AS DATE);

INSERT INTO shop_dm.dws_inventory_daily
SELECT
    product_id,
    store_id,
    snapshot_date AS stat_date,
    SUM(quantity) AS quantity,
    MAX(safety_stock) AS safety_stock,
    CASE
        WHEN SUM(quantity) <= 0 THEN '缺货'
        WHEN SUM(quantity) <= MAX(safety_stock) * 0.5 THEN '缺货预警'
        WHEN SUM(quantity) <= MAX(safety_stock) THEN '偏低'
        ELSE '正常'
    END AS stock_status,
    MAX(days_since_restock) AS days_since_restock,
    NOW() AS etl_time
FROM shop_dm.dwd_inventory
WHERE snapshot_date = CAST(@etl_date AS DATE)
GROUP BY product_id, store_id, snapshot_date;
