-- ============================================================
-- 加工作业: ADS 客户RFM分析表
-- 源表: dws_customer_order_summary
-- 加工逻辑: RFM指标计算 -> NTILE打分 -> 客户分层
-- ============================================================

-- Step 1: 清空目标表
TRUNCATE TABLE olist_dm.ads_customer_rfm;

-- Step 2: RFM 计算与分层
INSERT INTO olist_dm.ads_customer_rfm
WITH rfm_base AS (
    SELECT
        customer_id,
        MAX(stat_date) AS last_order_date,
        DATEDIFF(CURDATE(), MAX(stat_date)) AS recency_days,
        SUM(order_count) AS frequency,
        SUM(total_revenue) AS monetary
    FROM olist_dm.dws_customer_order_summary
    GROUP BY customer_id
),
rfm_scored AS (
    SELECT
        customer_id,
        recency_days,
        frequency,
        monetary,
        NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
        NTILE(5) OVER (ORDER BY frequency ASC) AS f_score,
        NTILE(5) OVER (ORDER BY monetary ASC) AS m_score
    FROM rfm_base
)
SELECT
    customer_id,
    CURDATE() AS stat_date,
    recency_days,
    frequency,
    monetary,
    r_score,
    f_score,
    m_score,
    r_score + f_score + m_score AS rfm_score,
    CASE
        WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN '高价值客户'
        WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3 THEN '重要保持客户'
        WHEN r_score >= 3 AND (f_score < 3 OR m_score < 3) THEN '重要发展客户'
        WHEN r_score < 3 AND f_score >= 3 AND m_score >= 3 THEN '重要挽留客户'
        WHEN r_score < 3 AND f_score < 3 AND m_score < 3 THEN '流失预警客户'
        ELSE '一般价值客户'
    END AS customer_segment,
    NOW() AS etl_time
FROM rfm_scored;

-- Step 3: 客户分层空值修正
UPDATE olist_dm.ads_customer_rfm
SET customer_segment = '一般价值客户'
WHERE customer_segment IS NULL;
