DROP TABLE IF EXISTS finance_analytics_dm.dwd_loan_payments;
-- table_id: d384a369-97ad-44ec-84af-6df572cd08fe
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dwd_loan_payments (
    -- column_id: f6b18eae-af94-4aa4-81a9-a2613df09c90
    payment_id BIGINT NULL,
    -- column_id: 701fe5bf-d8bf-45ae-8463-ad15c3f0591d
    account_id BIGINT NULL,
    -- column_id: 7f3f2cf4-b245-49f1-b177-f61e60ebe6fd
    customer_id BIGINT NULL,
    -- column_id: 8a897184-8cc9-4eb9-ae9b-309a433d3204
    scheduled_date DATETIME NULL,
    -- column_id: 72221cc9-f0fb-4311-8b5f-3948690844cd
    actual_date DATETIME NULL,
    -- column_id: 3051e79a-200c-4a10-8be1-e77ae038e277
    scheduled_amount DECIMAL(18,4) NULL,
    -- column_id: 4c471d1d-67b4-475f-a653-6b16679db926
    actual_amount DECIMAL(18,4) NULL,
    -- column_id: bcfb4419-bb47-49db-9e12-0b38af52a8b0
    is_late BOOLEAN NULL,
    -- column_id: 2b0e08fd-e2a8-41f4-9afe-76e99c064475
    days_late BIGINT NULL,
    -- column_id: 7ec9ea97-3204-4985-b6e6-357f33aa6dda
    late_fee DECIMAL(18,4) NULL,
    -- column_id: 525b4ce3-6b3e-4bf3-883d-cd87404c5562
    payment_method STRING NULL,
    -- column_id: 9fa41ab6-93ce-4776-a1c6-f4125c88d554
    outstanding_balance DECIMAL(18,4) NULL,
    -- column_id: e178cf97-5e90-4f91-9aa4-1339088b2d08
    payment_status STRING NULL,
    -- column_id: 9008a933-e319-442d-938f-1fb5621ab3cb
    payment_completeness STRING NULL,
    -- column_id: 3a61d28a-1fce-49a8-b157-ec00cbe8aeff
    amount_difference DECIMAL(18,4) NULL,
    -- column_id: 4580273d-a932-4b19-9570-72dcf07e16da
    delinquency_bucket STRING NULL,
    -- column_id: 270b438a-0a52-453e-b010-f46510d3a58a
    updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(payment_id)
DISTRIBUTED BY HASH(payment_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
