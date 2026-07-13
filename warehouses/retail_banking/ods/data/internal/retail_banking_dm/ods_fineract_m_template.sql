-- Deterministic smoke data for Fineract m_template
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_template;

INSERT INTO retail_banking_dm.ods_fineract_m_template (
    `id`,
    `name`,
    `text`,
    `entity`,
    `type`,
    `load_time`
) VALUES
    (
        1,
        'Synthetic m_template 1',
        'm_template_text_1',
        1,
        1,
        '2025-01-15 00:00:00'
    );
