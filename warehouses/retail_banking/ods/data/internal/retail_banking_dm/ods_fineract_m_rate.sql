-- Deterministic smoke data for Fineract m_rate
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_rate;

INSERT INTO retail_banking_dm.ods_fineract_m_rate (
    `id`,
    `name`,
    `percentage`,
    `active`,
    `product_apply`,
    `created_date`,
    `createdby_id`,
    `lastmodifiedby_id`,
    `lastmodified_date`,
    `approve_user`,
    `load_time`
) VALUES
    (
        1,
        'Synthetic m_rate 1',
        1,
        FALSE,
        1,
        '2025-01-15 09:00:00',
        1,
        1,
        '2025-01-15 09:00:00',
        1,
        '2025-01-15 00:00:00'
    );
