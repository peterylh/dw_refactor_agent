-- ============================================================
-- 加工作业: DWD 促销活动维度宽表 (每日快照)
-- 源表: ods_promotion
-- 加工逻辑: 计算持续天数 -> 判断是否进行中 -> 补全缺失值
-- 写入模式: 追加每日快照,按 snapshot_date 分区
-- ============================================================

SET @etl_date = COALESCE(@etl_date, CURDATE());
INSERT INTO shop_dm.dwd_promotion
SELECT
    promotion_id,
    CAST(@etl_date AS DATE) AS snapshot_date,
    NOW() AS etl_time,
    promotion_name,
    promotion_type,
    discount_rate,
    start_date,
    end_date,
    DATEDIFF(end_date, start_date) + 1 AS duration_days,
    min_amount,
    CASE
        WHEN CAST(@etl_date AS DATE) BETWEEN start_date AND end_date THEN 1
        ELSE 0
    END AS is_active,
    status
FROM (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY promotion_id ORDER BY load_time DESC) AS rn
    FROM shop_dm.ods_promotion
    WHERE DATE(load_time) <= CAST(@etl_date AS DATE)
) t
WHERE rn = 1;
