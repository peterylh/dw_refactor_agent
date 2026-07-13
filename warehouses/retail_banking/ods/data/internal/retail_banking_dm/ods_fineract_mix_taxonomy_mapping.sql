-- Deterministic smoke data for Fineract mix_taxonomy_mapping
TRUNCATE TABLE retail_banking_dm.ods_fineract_mix_taxonomy_mapping;

INSERT INTO retail_banking_dm.ods_fineract_mix_taxonomy_mapping (
    `id`,
    `identifier`,
    `config`,
    `last_update_date`,
    `currency`,
    `load_time`
) VALUES
    (
        1,
        'mix_taxonomy_mapping_identifier_1',
        '{}',
        '2025-01-15 09:00:00',
        'USD',
        '2025-01-15 00:00:00'
    );
