-- Deterministic smoke data for Fineract m_image
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_image;

INSERT INTO retail_banking_dm.ods_fineract_m_image (
    `id`,
    `location`,
    `storage_type_enum`,
    `load_time`
) VALUES
    (
        1,
        'm_image_location_1',
        1,
        '2025-01-15 00:00:00'
    );
