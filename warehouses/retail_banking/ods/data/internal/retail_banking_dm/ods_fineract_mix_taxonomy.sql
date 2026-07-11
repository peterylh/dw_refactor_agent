-- Deterministic smoke data for Fineract mix_taxonomy
TRUNCATE TABLE retail_banking_dm.ods_fineract_mix_taxonomy;

INSERT INTO retail_banking_dm.ods_fineract_mix_taxonomy (
    `id`,
    `name`,
    `namespace_id`,
    `dimension`,
    `type`,
    `description`,
    `need_mapping`,
    `load_time`
) VALUES
    (
        1,
        'Synthetic mix_taxonomy 1',
        1,
        'mix_taxonomy_dimension_1',
        1,
        'mix_taxonomy_description_1',
        FALSE,
        '2025-01-15 00:00:00'
    );
