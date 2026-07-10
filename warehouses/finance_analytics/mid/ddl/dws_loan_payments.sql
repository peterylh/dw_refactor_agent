DROP TABLE IF EXISTS finance_analytics_dm.dws_loan_payments;
-- table_id: 4783d403-7133-442b-ba4b-b1275dc1b18a
CREATE TABLE IF NOT EXISTS finance_analytics_dm.dws_loan_payments (
    -- column_id: b398a4d1-3394-4abe-964a-a8dce6f26b12
    payment_key CHAR(32) NULL,
    -- column_id: efa67df8-5e58-44b9-9efa-a79907227a17
    account_key CHAR(32) NULL,
    -- column_id: 0b189ed7-f9e2-42c1-bcd7-2f5c70695210
    customer_key CHAR(32) NULL,
    -- column_id: 083bb3f3-34f0-4cbb-8ee6-689b908fc300
    scheduled_date_key CHAR(32) NULL,
    -- column_id: 6b664460-c158-4e9b-89e6-39ab644c8651
    actual_date_key CHAR(32) NULL,
    -- column_id: 6056c5e0-31f4-45e6-9fcf-1f7fd24a0323
    payment_id BIGINT NULL,
    -- column_id: d17abe4a-09a3-4ad5-ae5e-73e5417a9e14
    scheduled_date DATETIME NULL,
    -- column_id: a026a640-eef0-4aab-9530-49920d65edd4
    actual_date DATETIME NULL,
    -- column_id: dda94e0d-2797-4b31-9a31-88da259ef102
    payment_status STRING NULL,
    -- column_id: 380388a1-ac13-494d-9653-c374d6cf4aae
    payment_method STRING NULL,
    -- column_id: 0491c097-0744-4904-b97c-662a38cab7c5
    payment_completeness STRING NULL,
    -- column_id: 1cf53da4-55e7-4884-92a2-94d822507a29
    delinquency_bucket STRING NULL,
    -- column_id: 2eb87a98-8dee-4fce-affd-439071fdedc4
    scheduled_amount DECIMAL(18,4) NULL,
    -- column_id: fec11aa8-0a81-480c-8b87-565afb0ebb27
    actual_amount DECIMAL(18,4) NULL,
    -- column_id: 27c4352e-c1cd-4c76-9dd2-8ba19998e48a
    amount_difference DECIMAL(18,4) NULL,
    -- column_id: 848daf0e-b47c-4b07-ae79-a334f50e9db6
    late_fee DECIMAL(18,4) NULL,
    -- column_id: b4b8ec49-cdd2-4610-a7fd-0026fb4a0ba1
    outstanding_balance DECIMAL(18,4) NULL,
    -- column_id: f7967730-adbb-4878-bc99-664188b61400
    days_late BIGINT NULL,
    -- column_id: 04fd254b-de20-49ff-987c-2c0bb8b8d2e6
    late_payment_flag BOOLEAN NULL,
    -- column_id: 36357f64-9043-4ec1-99fa-20f643233abd
    missed_payment_flag BOOLEAN NULL,
    -- column_id: e9dd8fe2-5533-4a16-a010-dc038abfb23c
    full_payment_flag BOOLEAN NULL,
    -- column_id: 4d0995d4-b2a8-45b2-a8fa-76016c482fef
    payment_count BIGINT NULL,
    -- column_id: 3c72a828-d3f9-4de7-a07f-c1d4fafaf2d7
    dbt_updated_at DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(payment_key)
DISTRIBUTED BY HASH(payment_key) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
