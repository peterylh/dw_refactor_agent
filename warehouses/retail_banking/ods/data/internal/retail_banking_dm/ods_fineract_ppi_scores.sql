-- Deterministic smoke data for Fineract ppi_scores
TRUNCATE TABLE retail_banking_dm.ods_fineract_ppi_scores;

INSERT INTO retail_banking_dm.ods_fineract_ppi_scores (
    `id`,
    `score_from`,
    `score_to`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        '2025-01-15 00:00:00'
    );
