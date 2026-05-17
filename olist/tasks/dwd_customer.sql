-- ============================================================
-- 加工作业: DWD 客户明细维表(纯维度)
-- 源表: ods_customer
-- 加工逻辑: 客户基本信息 -> 地理区域划分 -> 补全缺失值
-- ============================================================

-- Step 1: 清空目标表
TRUNCATE TABLE olist_dm.dwd_customer;

-- Step 2: 全量加载维度 + 区域划分
INSERT INTO olist_dm.dwd_customer
SELECT
    customer_id,
    customer_unique_id,
    customer_city,
    customer_state,
    CASE
        WHEN customer_state IN ('AC','AP','AM','PA','RO','RR','TO') THEN 'Norte'
        WHEN customer_state IN ('AL','BA','CE','MA','PB','PE','PI','RN','SE') THEN 'Nordeste'
        WHEN customer_state IN ('DF','GO','MT','MS') THEN 'Centro-Oeste'
        WHEN customer_state IN ('ES','MG','RJ','SP') THEN 'Sudeste'
        WHEN customer_state IN ('PR','RS','SC') THEN 'Sul'
        ELSE 'Desconhecido'
    END AS customer_region,
    NOW() AS etl_time
FROM olist_dm.ods_customer;

-- Step 3: 城市为空填充
UPDATE olist_dm.dwd_customer
SET customer_city = 'desconhecido'
WHERE customer_city IS NULL OR customer_city = '';

-- Step 4: 区域为空填充
UPDATE olist_dm.dwd_customer
SET customer_region = 'Desconhecido'
WHERE customer_region IS NULL;
