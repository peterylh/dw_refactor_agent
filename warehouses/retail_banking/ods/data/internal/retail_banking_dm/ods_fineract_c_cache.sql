-- Deterministic smoke data for Fineract c_cache
TRUNCATE TABLE retail_banking_dm.ods_fineract_c_cache;

INSERT INTO retail_banking_dm.ods_fineract_c_cache (
    `id`,
    `cache_type_enum`,
    `load_time`
) VALUES
    (
        1,
        1,
        '2025-01-15 00:00:00'
    );
