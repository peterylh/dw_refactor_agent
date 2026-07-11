-- Deterministic smoke data for Fineract ppi_likelihoods
TRUNCATE TABLE retail_banking_dm.ods_fineract_ppi_likelihoods;

INSERT INTO retail_banking_dm.ods_fineract_ppi_likelihoods (
    `id`,
    `code`,
    `name`,
    `load_time`
) VALUES
    (
        1,
        'ppi_likelihoods_code_1',
        'Synthetic ppi_likelihoods 1',
        '2025-01-15 00:00:00'
    );
