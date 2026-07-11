-- Deterministic smoke data for Fineract ppi_likelihoods_ppi
TRUNCATE TABLE retail_banking_dm.ods_fineract_ppi_likelihoods_ppi;

INSERT INTO retail_banking_dm.ods_fineract_ppi_likelihoods_ppi (
    `id`,
    `likelihood_id`,
    `ppi_name`,
    `enabled`,
    `load_time`
) VALUES
    (
        1,
        1,
        'ppi_likelihoods_ppi_ppi_name_1',
        1,
        '2025-01-15 00:00:00'
    );
