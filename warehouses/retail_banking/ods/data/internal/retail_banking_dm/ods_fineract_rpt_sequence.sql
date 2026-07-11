-- Deterministic smoke data for Fineract rpt_sequence
TRUNCATE TABLE retail_banking_dm.ods_fineract_rpt_sequence;

INSERT INTO retail_banking_dm.ods_fineract_rpt_sequence (
    `id`,
    `load_time`
) VALUES
    (
        1,
        '2025-01-15 00:00:00'
    );
