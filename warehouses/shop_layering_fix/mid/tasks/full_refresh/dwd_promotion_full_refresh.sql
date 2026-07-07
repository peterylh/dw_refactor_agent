-- ============================================================
-- 加工作业: DWD 促销活动维度宽表 (批量全量刷新)
-- 源表: ods_promotion
-- 加工逻辑: 按 promotion_id + DATE(load_time) 生成所有日快照
-- 写入模式: 一次 INSERT 全部历史快照
-- ============================================================

INSERT INTO shop_dm.dwd_promotion
SELECT
    promotion_id,
    DATE(load_time) AS snapshot_date,
    NOW() AS etl_time,
    promotion_name,
    promotion_type,
    discount_rate,
    start_date,
    end_date,
    DATEDIFF(end_date, start_date) + 1 AS duration_days,
    min_amount,
    CASE
        WHEN DATE(load_time) BETWEEN start_date AND end_date THEN 1
        ELSE 0
    END AS is_active,
    status
FROM (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY promotion_id, DATE(load_time) ORDER BY load_time DESC) AS rn
    FROM shop_dm.ods_promotion
) t
WHERE rn = 1;
