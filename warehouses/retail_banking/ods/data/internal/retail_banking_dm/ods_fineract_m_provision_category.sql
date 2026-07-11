-- Deterministic smoke data for Fineract m_provision_category
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_provision_category;

INSERT INTO retail_banking_dm.ods_fineract_m_provision_category (
    `id`,
    `category_name`,
    `description`,
    `load_time`
) VALUES
    (
        1,
        'm_provision_category_category_name_1',
        'm_provision_category_description_1',
        '2025-01-15 00:00:00'
    );
