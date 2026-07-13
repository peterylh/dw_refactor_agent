DROP TABLE IF EXISTS finance_analytics_dm.dim_date;
-- table_id: daffc166-3c15-44b3-b4d7-47eb5664525d
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dim_date (
    -- column_id: 6f226a38-febf-46de-8ad8-6e9d01b3bb26
    date_key CHAR(32) NULL,
    -- column_id: ca5212f2-40ee-40ae-8005-cf082c287368
    date_actual DATETIME NULL,
    -- column_id: 8cdb843e-58a5-4ee3-ae03-ef519cb78167
    year BIGINT NULL,
    -- column_id: 1682e78b-c710-4c02-b967-699d82fc05d5
    quarter BIGINT NULL,
    -- column_id: 0e4612b8-e0aa-4e49-921d-11b12d871489
    month BIGINT NULL,
    -- column_id: 2c7158d4-9806-4369-b8f4-3bb78207edc4
    week_of_year BIGINT NULL,
    -- column_id: b64908af-5f19-408c-8977-08bc4c9b2876
    day_of_year BIGINT NULL,
    -- column_id: 070a3f62-b855-42d8-94c4-bdbc23d1f9f3
    day_of_week BIGINT NULL,
    -- column_id: a6124e2f-2f83-481e-8a23-0bd0db40d0f0
    day_name STRING NULL,
    -- column_id: bb6e1819-3318-4d7a-a89c-d9bb9677b1e7
    month_name STRING NULL,
    -- column_id: 943c4334-d988-4c32-88d5-b019f5b81ba7
    year_month STRING NULL,
    -- column_id: ab191959-e3ca-4d9f-b9d9-2c2a34cb90e8
    year_quarter STRING NULL,
    -- column_id: 6b774849-859d-4fde-9eeb-4ae2d4b72545
    is_weekend BOOLEAN NULL,
    -- column_id: cae0bb1e-b849-49a2-be02-f1b7acdcf162
    is_sunday BOOLEAN NULL,
    -- column_id: 44138d87-77b9-48fe-ae77-f8e518c1652d
    is_saturday BOOLEAN NULL,
    -- column_id: 75cdb3ce-e8cb-4942-baf5-920b16ad6075
    first_day_of_month STRING NULL,
    -- column_id: 13aab831-8ee6-4c32-95fc-27a1244f3576
    last_day_of_month STRING NULL,
    -- column_id: 2402f333-18f3-4a8e-900c-50ef214ef205
    first_day_of_quarter STRING NULL,
    -- column_id: 6a923c8a-8049-4ada-8ee2-6dd433ed1cda
    last_day_of_quarter STRING NULL,
    -- column_id: 7c50d3d6-d828-4929-9437-6ada2596e4ba
    first_day_of_year STRING NULL,
    -- column_id: 748f23e9-77c5-46b4-9246-1c1ae53fc99f
    last_day_of_year STRING NULL,
    -- column_id: d24351cd-4fd4-402b-ac32-c95c192ee81f
    is_first_day_of_month BOOLEAN NULL,
    -- column_id: dcb4d550-879c-4903-ba8e-ae0d5679c99a
    is_last_day_of_month BOOLEAN NULL
) ENGINE=OLAP
DUPLICATE KEY(date_key)
DISTRIBUTED BY HASH(date_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
