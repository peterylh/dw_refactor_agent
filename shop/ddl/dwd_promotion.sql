-- DWD 促销活动维度宽表
-- table_id: f1a2b3c4-d5e6-4f7a-8b9c-0d1e2f3a4b5c
DROP TABLE IF EXISTS shop_dm.dwd_promotion;
CREATE TABLE IF NOT EXISTS shop_dm.dwd_promotion (
    promotion_id   BIGINT        NOT NULL COMMENT '促销ID',
    snapshot_date  DATE          NOT NULL COMMENT '快照日期',
    etl_time       DATETIME      NOT NULL COMMENT 'ETL处理时间',
    promotion_name VARCHAR(128)  NOT NULL COMMENT '促销名称',
    promotion_type VARCHAR(32)   NOT NULL COMMENT '促销类型:满减/折扣/买赠/秒杀',
    discount_rate  DECIMAL(5,2)  NULL COMMENT '折扣率',
    start_date     DATE          NOT NULL COMMENT '开始日期',
    end_date       DATE          NOT NULL COMMENT '结束日期',
    duration_days  INT           NULL COMMENT '活动持续天数',
    min_amount     DECIMAL(12,2) NULL COMMENT '最低消费金额',
    is_active      TINYINT       NULL COMMENT '是否进行中:1是/0否',
    status         TINYINT       NOT NULL DEFAULT 1 COMMENT '状态'
) ENGINE=OLAP
UNIQUE KEY(promotion_id, snapshot_date)
PARTITION BY RANGE(snapshot_date) (
    PARTITION p20240601 VALUES LESS THAN ("2024-06-02")
)
DISTRIBUTED BY HASH(promotion_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1",
    "dynamic_partition.enable" = "true",
    "dynamic_partition.time_unit" = "DAY",
    "dynamic_partition.start" = "-365",
    "dynamic_partition.end" = "3",
    "dynamic_partition.prefix" = "p",
    "dynamic_partition.buckets" = "1"
);
