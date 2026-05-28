-- DWD 客户明细宽表
-- table_id: 3cacec5e-705c-430a-ae82-b6b0915d9096
DROP TABLE IF EXISTS shop_dm.dwd_customer;
CREATE TABLE IF NOT EXISTS shop_dm.dwd_customer (
    customer_id    BIGINT       NOT NULL COMMENT '客户ID',
    snapshot_date  DATE         NOT NULL COMMENT '快照日期',
    etl_time       DATETIME     NOT NULL COMMENT 'ETL处理时间',
    customer_name  VARCHAR(64)  NOT NULL COMMENT '客户姓名',
    gender         VARCHAR(4)   NULL COMMENT '性别',
    age            INT          NULL COMMENT '年龄',
    age_group      VARCHAR(16)  NULL COMMENT '年龄段:青年/中年/中老年/老年',
    phone          VARCHAR(20)  NULL COMMENT '手机号',
    email          VARCHAR(128) NULL COMMENT '邮箱',
    address        VARCHAR(256) NULL COMMENT '地址',
    city           VARCHAR(64)  NULL COMMENT '城市',
    province       VARCHAR(64)  NULL COMMENT '省份',
    member_level   VARCHAR(16)  NULL COMMENT '会员等级',
    register_date  DATE         NULL COMMENT '注册日期'
) ENGINE=OLAP
UNIQUE KEY(customer_id, snapshot_date)
PARTITION BY RANGE(snapshot_date) (
    PARTITION p20240601 VALUES LESS THAN ("2024-06-02")
)
DISTRIBUTED BY HASH(customer_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1",
    "dynamic_partition.enable" = "true",
    "dynamic_partition.time_unit" = "DAY",
    "dynamic_partition.start" = "-365",
    "dynamic_partition.end" = "3",
    "dynamic_partition.prefix" = "p",
    "dynamic_partition.buckets" = "1"
);
