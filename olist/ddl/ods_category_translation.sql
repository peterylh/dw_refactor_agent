-- ODS Olist 品类名称翻译表
DROP TABLE IF EXISTS olist_dm.ods_category_translation;
CREATE TABLE IF NOT EXISTS olist_dm.ods_category_translation (
    product_category_name            VARCHAR(64) NOT NULL COMMENT '品类葡萄牙语名称',
    product_category_name_english    VARCHAR(64) NOT NULL COMMENT '品类英语名称'
) ENGINE=OLAP
DUPLICATE KEY(product_category_name)
DISTRIBUTED BY HASH(product_category_name) BUCKETS 10
PROPERTIES ("replication_num" = "1");

INSERT INTO olist_dm.ods_category_translation VALUES
('fashion_bolsas_e_acessorios', 'fashion_bags_and_accessories'),
('cama_mesa_banho', 'bed_bath_table'),
('moveis_decoracao', 'furniture_decor'),
('beleza_saude', 'health_beauty'),
('informatica_acessorios', 'computers_accessories'),
('brinquedos', 'toys'),
('automotivo', 'auto'),
('livros_interesse_geral', 'books_general_interest'),
('esporte_lazer', 'sports_leisure'),
('alimentos_bebidas', 'food_drinks');
