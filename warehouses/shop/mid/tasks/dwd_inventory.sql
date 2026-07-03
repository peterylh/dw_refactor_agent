-- ============================================================
-- 加工作业: DWD 库存快照宽表 (每日快照)
-- 源表: ods_inventory
-- 加工逻辑: 计算库存状态 -> 计算距上次补货天数
-- 写入模式: 追加每日快照,按 snapshot_date 分区
-- ============================================================

SET @etl_date = COALESCE(@etl_date, CURDATE());
INSERT INTO shop_dm.dwd_inventory
SELECT
    inventory_id,
    CAST(@etl_date AS DATE) AS snapshot_date,
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
    DATEDIFF(CAST(@etl_date AS DATE), last_restock_date) AS days_since_restock
FROM (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY inventory_id ORDER BY load_time DESC) AS rn
    FROM shop_dm.ods_inventory
    WHERE DATE(load_time) <= CAST(@etl_date AS DATE)
) t
WHERE rn = 1;
