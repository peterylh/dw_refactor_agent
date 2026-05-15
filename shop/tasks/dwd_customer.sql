-- ============================================================
-- 加工作业: DWD 客户明细宽表
-- 源表: ods_customer
-- 加工逻辑: 清洗客户数据 -> 划分年龄段 -> 补全缺失值
-- ============================================================

-- Step 1: 清空目标表(全量刷新)
TRUNCATE TABLE shop_dm.dwd_customer;

-- Step 2: 全量加载 + 年龄段派生
INSERT INTO shop_dm.dwd_customer
SELECT
    customer_id,
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
    province,
    member_level,
    register_date,
    NOW() AS etl_time
FROM shop_dm.ods_customer
WHERE customer_name IS NOT NULL;

-- Step 3: 会员等级为空时设为普通会员
UPDATE shop_dm.dwd_customer
SET member_level = '普通'
WHERE member_level IS NULL OR member_level = '';

-- Step 4: 省份为空时根据城市映射补齐
UPDATE shop_dm.dwd_customer
SET province = CASE
    WHEN city = '北京' THEN '北京'
    WHEN city = '上海' THEN '上海'
    WHEN city IN ('广州','深圳') THEN '广东'
    WHEN city = '成都' THEN '四川'
    WHEN city = '杭州' THEN '浙江'
    WHEN city = '重庆' THEN '重庆'
    WHEN city = '南京' THEN '江苏'
    WHEN city = '济南' THEN '山东'
    WHEN city = '天津' THEN '天津'
    ELSE province
END
WHERE province IS NULL;
