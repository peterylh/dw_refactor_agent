-- ODS 促销活动表
-- table_id: 1b96955c-e1c0-48a7-85ee-b5c5078bc741
DROP TABLE IF EXISTS shop_dm.ods_promotion;
CREATE TABLE IF NOT EXISTS shop_dm.ods_promotion (
    promotion_id   BIGINT        NOT NULL COMMENT '促销ID',
    promotion_name VARCHAR(128)  NOT NULL COMMENT '促销名称',
    promotion_type VARCHAR(32)   NOT NULL COMMENT '促销类型:满减/折扣/买赠/秒杀',
    discount_rate  DECIMAL(5,2)  NULL COMMENT '折扣率',
    start_date     DATE          NOT NULL COMMENT '开始日期',
    end_date       DATE          NOT NULL COMMENT '结束日期',
    min_amount     DECIMAL(12,2) NULL COMMENT '最低消费金额',
    status         TINYINT       NOT NULL DEFAULT 1 COMMENT '状态:1进行中/0已结束',
    create_time    DATETIME      NOT NULL COMMENT '创建时间'
) ENGINE=OLAP
DUPLICATE KEY(promotion_id)
PARTITION BY RANGE(create_time) (
    PARTITION p20250101 VALUES LESS THAN ("2025-01-02"),
    PARTITION p20250102 VALUES LESS THAN ("2025-01-03"),
    PARTITION p20250103 VALUES LESS THAN ("2025-01-04"),
    PARTITION p_future VALUES LESS THAN MAXVALUE
)
DISTRIBUTED BY HASH(promotion_id) BUCKETS 10
PROPERTIES (
    "replication_num" = "1"
);

INSERT INTO shop_dm.ods_promotion VALUES
(4001, '元旦满减',     '满减', NULL,    '2025-01-01', '2025-01-03', 200.00, 0, '2025-01-01 08:00:00'),
(4002, '春节大促',     '折扣', 0.85,    '2025-01-28', '2025-02-05', NULL,   0, '2025-01-01 08:00:00'),
(4003, '三八女神节',   '折扣', 0.80,    '2025-03-06', '2025-03-10', NULL,   0, '2025-01-02 08:00:00'),
(4004, '五一欢乐购',   '满减', NULL,    '2025-05-01', '2025-05-05', 300.00, 1, '2025-01-02 08:00:00'),
(4005, '618年中大促',  '折扣', 0.75,    '2025-06-15', '2025-06-20', NULL,   0, '2025-01-02 08:00:00'),
(4006, '中秋团圆惠',   '买赠', NULL,    '2025-09-25', '2025-10-01', 150.00, 0, '2025-01-03 08:00:00'),
(4007, '双十一狂欢',   '秒杀', 0.50,    '2025-11-10', '2025-11-12', NULL,   0, '2025-01-03 08:00:00');
