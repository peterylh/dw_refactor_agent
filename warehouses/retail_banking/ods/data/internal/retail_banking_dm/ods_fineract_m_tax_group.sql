-- Deterministic smoke data for Fineract m_tax_group
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_tax_group;

INSERT INTO retail_banking_dm.ods_fineract_m_tax_group (
    `id`,
    `name`,
    `createdby_id`,
    `created_date`,
    `lastmodifiedby_id`,
    `lastmodified_date`,
    `load_time`
) VALUES
    (
        1,
        'Synthetic m_tax_group 1',
        1,
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
