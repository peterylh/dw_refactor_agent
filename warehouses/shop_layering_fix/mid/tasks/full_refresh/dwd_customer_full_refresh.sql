-- ============================================================
-- 加工作业: DWD 客户明细宽表 (批量全量刷新)
-- 源表: ods_customer
-- 加工逻辑: 按 customer_id + DATE(load_time) 生成所有日快照
-- 写入模式: 一次 INSERT 全部历史快照
-- ============================================================

-- Step 1: 批量生成所有日快照
INSERT INTO shop_dm.dwd_customer
SELECT
    customer_id,
    DATE(load_time) AS snapshot_date,
    NOW() AS etl_time,
    customer_name,
    gender,
    age,
    CASE
        WHEN age < 30 THEN '青年'
        WHEN age < 45 THEN '中年'
        WHEN age < 60 THEN '中老年'
        ELSE '老年'
    END AS age_group,
    phone,
    email,
    address,
    city,
    COALESCE(
        CASE
            WHEN city = '北京' THEN '北京'
            WHEN city = '上海' THEN '上海'
            WHEN city IN ('广州','深圳') THEN '广东'
            WHEN city = '成都' THEN '四川'
            WHEN city = '杭州' THEN '浙江'
            WHEN city = '重庆' THEN '重庆'
            WHEN city = '南京' THEN '江苏'
            WHEN city = '济南' THEN '山东'
            WHEN city = '天津' THEN '天津'
        END,
        province
    ) AS province,
    COALESCE(NULLIF(member_level, ''), '普通') AS member_level,
    register_date
FROM (
    SELECT *,
        ROW_NUMBER() OVER (PARTITION BY customer_id, DATE(load_time) ORDER BY load_time DESC) AS rn
    FROM shop_dm.ods_customer
    WHERE customer_name IS NOT NULL
) t
WHERE rn = 1;
