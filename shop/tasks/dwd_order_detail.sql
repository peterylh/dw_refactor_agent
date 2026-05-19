-- ============================================================
-- 加工作业: DWD 订单明细事实表
-- 源表: ods_order, ods_order_item, ods_product
-- 加工逻辑: 多表关联 -> 计算毛利 -> 回填成本 -> 剔除无效订单
-- 写入模式: 全量刷新,按 order_date 分区
-- ============================================================

-- Step 1: 清空目标表
TRUNCATE TABLE shop_dm.dwd_order_detail;

-- Step 2: 关联订单主表、明细表、商品表，构建订单明细宽表
INSERT INTO shop_dm.dwd_order_detail
SELECT
    o.order_id,
    oi.order_item_id,
    o.order_date,
    o.customer_id,
    o.store_id,
    oi.product_id,
    p.category_id,
    o.promotion_id,
    DATE_FORMAT(o.order_date, '%Y-%m') AS order_month,
    oi.quantity,
    oi.unit_price,
    oi.discount,
    oi.subtotal,
    p.cost_price,
    ROUND(oi.subtotal - p.cost_price * oi.quantity, 2) AS gross_profit,
    o.payment_method,
    o.order_status,
    NOW() AS etl_time
FROM shop_dm.ods_order o
INNER JOIN shop_dm.ods_order_item oi ON o.order_id = oi.order_id
LEFT JOIN shop_dm.ods_product p ON oi.product_id = p.product_id
WHERE o.order_status = '已完成';

-- Step 3: 商品维表关联缺失导致成本为空时，用售价×60%估算成本
UPDATE shop_dm.dwd_order_detail
SET cost_price = ROUND(unit_price * 0.60, 2)
WHERE cost_price IS NULL;

-- Step 4: 重新计算毛利(成本回填后)
UPDATE shop_dm.dwd_order_detail
SET gross_profit = ROUND(subtotal - cost_price * quantity, 2);

-- Step 5: 支付方式为空时标记为"未知"
UPDATE shop_dm.dwd_order_detail
SET payment_method = '未知'
WHERE payment_method IS NULL OR payment_method = '';
