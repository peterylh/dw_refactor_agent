-- Deterministic smoke data for Fineract m_office
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_office;

INSERT INTO retail_banking_dm.ods_fineract_m_office (
    `id`,
    `parent_id`,
    `hierarchy`,
    `external_id`,
    `name`,
    `opening_date`,
    `load_time`
) VALUES
    (
        1,
        1,
        'm_office_hierarchy_1',
        '00000000-0000-4000-8000-000000000001',
        'Synthetic m_office 1',
        '2025-01-15',
        '2025-01-15 00:00:00'
    );
