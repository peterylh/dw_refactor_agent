-- Deterministic smoke data for Fineract m_hook_templates
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_hook_templates;

INSERT INTO retail_banking_dm.ods_fineract_m_hook_templates (
    `id`,
    `name`,
    `load_time`
) VALUES
    (
        1,
        'Synthetic m_hook_templates 1',
        '2025-01-15 00:00:00'
    );
