-- ============================================================
-- 加工作业: DWD 库存快照宽表 (批量全量刷新)
-- 源表: ods_inventory
-- 加工逻辑: 按 inventory_id + DATE(load_time) 生成所有日快照
-- 写入模式: 一次 INSERT 全部历史快照
-- ============================================================

INSERT INTO shop_dm.dwd_inventory
SELECT
    inventory_id,
    DATE(load_time) AS snapshot_date,
    NOW() AS etl_time,
    product_id,
    store_id,
    quantity,
    safety_stock,
    CASE
        WHEN quantity <= 0 THEN '缺货'
        WHEN quantity <= safety_stock * 0.5 THEN '缺货预警'
        WHEN quantity <= safety_stock THEN '偏低'
        ELSE '正常'
    END AS stock_status,
    last_restock_date,
    DATEDIFF(DATE(load_time), last_restock_date) AS days_since_restock
FROM (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY inventory_id, DATE(load_time) ORDER BY load_time DESC) AS rn
    FROM shop_dm.ods_inventory
) t
WHERE rn = 1;
