-- Deterministic smoke data for Fineract m_templatemappers
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_templatemappers;

INSERT INTO retail_banking_dm.ods_fineract_m_templatemappers (
    `id`,
    `mapperkey`,
    `mapperorder`,
    `mappervalue`,
    `load_time`
) VALUES
    (
        1,
        'm_templatemappers_mapperkey_1',
        1,
        'm_templatemappers_mappervalue_1',
        '2025-01-15 00:00:00'
    );
