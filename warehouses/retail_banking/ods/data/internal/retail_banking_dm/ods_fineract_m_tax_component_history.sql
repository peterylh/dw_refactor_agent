-- Deterministic smoke data for Fineract m_tax_component_history
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_tax_component_history;

INSERT INTO retail_banking_dm.ods_fineract_m_tax_component_history (
    `id`,
    `tax_component_id`,
    `percentage`,
    `start_date`,
    `end_date`,
    `createdby_id`,
    `created_date`,
    `lastmodifiedby_id`,
    `lastmodified_date`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        '2025-01-15',
        '2025-01-15',
        1,
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 09:00:00',
        '2025-01-15 00:00:00'
    );
