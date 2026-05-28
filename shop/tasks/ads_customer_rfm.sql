-- ============================================================
-- 加工作业: ADS 客户RFM分析表
-- 源表: dws_customer_order_summary
-- 加工逻辑: 计算RFM指标 -> NTILE打分 -> 客户分层 -> 填充默认值
-- 写入模式: 按 stat_date 分区, DELETE + INSERT 按日处理
-- ============================================================

SET @etl_date = COALESCE(@etl_date, CURDATE());
-- Step 1: 删除当前统计日期的数据
DELETE FROM shop_dm.ads_customer_rfm WHERE stat_date = CAST(@etl_date AS DATE);

-- Step 2: 计算 RFM 指标 + NTILE 分项评分 + 综合评分 + 客户分层
INSERT INTO shop_dm.ads_customer_rfm
WITH rfm_base AS (
    SELECT
        customer_id,
        MAX(stat_date) AS last_order_date,
        DATEDIFF(CAST(@etl_date AS DATE), MAX(stat_date)) AS recency_days,
        SUM(order_count) AS frequency,
        SUM(payment_amount) AS monetary
    FROM shop_dm.dws_customer_order_summary
    WHERE stat_date <= CAST(@etl_date AS DATE)
    GROUP BY customer_id
),
rfm_scored AS (
    SELECT
        customer_id,
        recency_days,
        frequency,
        monetary,
        -- R分值: 最近消费越近分数越高(DESC: 高recency→低分, 低recency→高分)
        NTILE(5) OVER (ORDER BY recency_days DESC) AS r_score,
        -- F分值: 消费频次越高分数越高(ASC: 低频次→低分, 高频次→高分)
        NTILE(5) OVER (ORDER BY frequency ASC) AS f_score,
        -- M分值: 消费金额越高分数越高(ASC: 低金额→低分, 高金额→高分)
        NTILE(5) OVER (ORDER BY monetary ASC) AS m_score
    FROM rfm_base
)
SELECT
    customer_id,
    CAST(@etl_date AS DATE) AS stat_date,
    recency_days,
    frequency,
    monetary,
    r_score,
    f_score,
    m_score,
    r_score + f_score + m_score AS rfm_score,
    CASE
        -- 高价值: 三个维度都在前40%(得分>=4)
        WHEN r_score >= 4 AND f_score >= 4 AND m_score >= 4 THEN '高价值客户'
        -- 重要保持: 三个维度中等偏上(得分>=3)
        WHEN r_score >= 3 AND f_score >= 3 AND m_score >= 3 THEN '重要保持客户'
        -- 重要发展: 最近来过但消费金额/频次不足
        WHEN r_score >= 3 AND (f_score < 3 OR m_score < 3) THEN '重要发展客户'
        -- 重要挽留: 很久没来但曾经消费多
        WHEN r_score < 3 AND f_score >= 3 AND m_score >= 3 THEN '重要挽留客户'
        -- 流失预警: 三个维度都偏低
        WHEN r_score < 3 AND f_score < 3 AND m_score < 3 THEN '流失预警客户'
        -- 新客户: 频次低但最近来过且消费不低
        WHEN f_score <= 2 AND r_score >= 3 AND m_score >= 3 THEN '新晋优质客户'
        ELSE '一般价值客户'
    END AS customer_segment,
    NOW() AS etl_time
FROM rfm_scored;

-- Step 3: 客户分层为空时标记为一般价值客户
UPDATE shop_dm.ads_customer_rfm
SET customer_segment = '一般价值客户'
WHERE customer_segment IS NULL
  AND stat_date = CAST(@etl_date AS DATE);
