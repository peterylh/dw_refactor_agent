-- Deterministic smoke data for Fineract m_hook
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_hook;

INSERT INTO retail_banking_dm.ods_fineract_m_hook (
    `id`,
    `template_id`,
    `is_active`,
    `name`,
    `createdby_id`,
    `created_date`,
    `lastmodifiedby_id`,
    `lastmodified_date`,
    `ugd_template_id`,
    `load_time`
) VALUES
    (
        1,
        1,
        FALSE,
        'Synthetic m_hook 1',
        1,
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 00:00:00'
    );
