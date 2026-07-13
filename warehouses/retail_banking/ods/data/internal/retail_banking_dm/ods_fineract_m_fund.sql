-- Deterministic smoke data for Fineract m_fund
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_fund;

INSERT INTO retail_banking_dm.ods_fineract_m_fund (
    `id`,
    `name`,
    `external_id`,
    `load_time`
) VALUES
    (
        1,
        'Synthetic m_fund 1',
        '00000000-0000-4000-8000-000000000001',
        '2025-01-15 00:00:00'
    );
