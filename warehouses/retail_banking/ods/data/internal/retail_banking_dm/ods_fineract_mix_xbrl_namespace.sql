-- Deterministic smoke data for Fineract mix_xbrl_namespace
TRUNCATE TABLE retail_banking_dm.ods_fineract_mix_xbrl_namespace;

INSERT INTO retail_banking_dm.ods_fineract_mix_xbrl_namespace (
    `id`,
    `prefix`,
    `url`,
    `load_time`
) VALUES
    (
        1,
        'mix_xbrl_namespace_p',
        'mix_xbrl_namespace_url_1',
        '2025-01-15 00:00:00'
    );
