-- Deterministic smoke data for Fineract acc_rule_tags
TRUNCATE TABLE retail_banking_dm.ods_fineract_acc_rule_tags;

INSERT INTO retail_banking_dm.ods_fineract_acc_rule_tags (
    `id`,
    `acc_rule_id`,
    `tag_id`,
    `acc_type_enum`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        '2025-01-15 00:00:00'
    );
