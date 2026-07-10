DROP TABLE IF EXISTS finance_analytics_dm.ods_loan_payments;
-- table_id: f45568e0-8027-4111-9e59-8ac0405e130a
CREATE TABLE IF NOT EXISTS finance_analytics_dm.ods_loan_payments (
    -- column_id: 79c40b64-0d2a-435a-ad77-3d4afaa033a2
    payment_id BIGINT NULL,
    -- column_id: ae7d822d-0b25-46e9-975f-d16e73183c6b
    account_id BIGINT NULL,
    -- column_id: b0cd9585-0e46-40d4-aeb5-946c458cffa9
    customer_id BIGINT NULL,
    -- column_id: 75003314-308c-48a0-b090-73139fdb5e3d
    scheduled_date DATETIME NULL,
    -- column_id: 5cd6c587-ff08-4a86-8f4d-f407f0125faa
    actual_date DATETIME NULL,
    -- column_id: 1c915638-e562-4651-94cd-e98f0fecc917
    scheduled_amount DECIMAL(18,4) NULL,
    -- column_id: eff6ba7f-66c0-4e21-878a-844688606289
    actual_amount DECIMAL(18,4) NULL,
    -- column_id: f231d81b-be57-444a-b533-f95bec64b6f3
    is_late BOOLEAN NULL,
    -- column_id: c0fbf8f9-5a8c-4204-ab79-0ea6220ebadb
    days_late BIGINT NULL,
    -- column_id: c41fb16c-9dde-4b43-ac00-8655ed9f944b
    late_fee DECIMAL(18,4) NULL,
    -- column_id: c0bb4cc3-e1f5-46c0-bacc-d60f260e5417
    payment_method STRING NULL,
    -- column_id: fda24903-d26a-440f-8a16-20c31d63de1c
    outstanding_balance DECIMAL(18,4) NULL,
    -- column_id: 06c486d9-82cc-4468-828e-2fdb57b447ae
    created_at DATETIME NULL,
    -- column_id: 692e60ca-8884-4967-a1a9-f153dcc86077
    load_time DATETIME NULL
) ENGINE=OLAP
DUPLICATE KEY(payment_id)
DISTRIBUTED BY HASH(payment_id) BUCKETS 1
PROPERTIES (
    "replication_num" = "1"
);
