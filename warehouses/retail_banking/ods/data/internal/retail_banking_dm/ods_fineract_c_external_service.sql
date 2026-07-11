-- Deterministic smoke data for Fineract c_external_service
TRUNCATE TABLE retail_banking_dm.ods_fineract_c_external_service;

INSERT INTO retail_banking_dm.ods_fineract_c_external_service (
    `id`,
    `name`,
    `load_time`
) VALUES
    (
        1,
        'Synthetic c_external_service 1',
        '2025-01-15 00:00:00'
    );
