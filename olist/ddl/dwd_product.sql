-- DWD Olist 商品明细维表
DROP TABLE IF EXISTS olist_dm.dwd_product;
CREATE TABLE IF NOT EXISTS olist_dm.dwd_product (
    product_id               VARCHAR(64)  NOT NULL COMMENT '商品ID',
    product_category_name    VARCHAR(64)  NULL COMMENT '商品品类(葡萄牙语)',
    product_category_name_english VARCHAR(64) NULL COMMENT '商品品类(英语)',
    product_name_length      INT          NULL COMMENT '商品名称长度',
    product_description_length INT        NULL COMMENT '商品描述长度',
    product_photos_qty       INT          NULL COMMENT '商品图片数量',
    product_weight_g         DECIMAL(10,2) NULL COMMENT '商品重量(克)',
    product_length_cm        DECIMAL(10,2) NULL COMMENT '商品长度(厘米)',
    product_height_cm        DECIMAL(10,2) NULL COMMENT '商品高度(厘米)',
    product_width_cm         DECIMAL(10,2) NULL COMMENT '商品宽度(厘米)',
    product_volume_cm3       DECIMAL(10,2) NULL COMMENT '商品体积(立方厘米)',
    product_weight_class     VARCHAR(32)  NULL COMMENT '重量等级:轻/中/重/超重',
    etl_time                 DATETIME     NOT NULL COMMENT 'ETL处理时间'
) ENGINE=OLAP
UNIQUE KEY(product_id)
DISTRIBUTED BY HASH(product_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
