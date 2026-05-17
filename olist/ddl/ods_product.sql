-- ODS Olist 商品信息表
DROP TABLE IF EXISTS olist_dm.ods_product;
CREATE TABLE IF NOT EXISTS olist_dm.ods_product (
    product_id               VARCHAR(64)  NOT NULL COMMENT '商品ID',
    product_category_name    VARCHAR(64)  NULL COMMENT '商品品类名称(葡萄牙语)',
    product_name_lenght      INT          NULL COMMENT '商品名称长度',
    product_description_lenght INT        NULL COMMENT '商品描述长度',
    product_photos_qty       INT          NULL COMMENT '商品图片数量',
    product_weight_g         DECIMAL(10,2) NULL COMMENT '商品重量(克)',
    product_length_cm        DECIMAL(10,2) NULL COMMENT '商品长度(厘米)',
    product_height_cm        DECIMAL(10,2) NULL COMMENT '商品高度(厘米)',
    product_width_cm         DECIMAL(10,2) NULL COMMENT '商品宽度(厘米)'
) ENGINE=OLAP
DUPLICATE KEY(product_id)
DISTRIBUTED BY HASH(product_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");

INSERT INTO olist_dm.ods_product VALUES
('99a4788cb24856965c36a24e339b6058', 'fashion_bolsas_e_acessorios', 27, 242, 1, 200.00, 26.00, 8.00, 18.00),
('e5a5a36a10b770a434cdabdffe57c3b2', 'cama_mesa_banho', 50, 928, 2, 600.00, 40.00, 15.00, 30.00),
('785546fb8ab0a484607add1ba1be23f7', 'moveis_decoracao', 22, 386, 1, 3500.00, 70.00, 10.00, 20.00);
