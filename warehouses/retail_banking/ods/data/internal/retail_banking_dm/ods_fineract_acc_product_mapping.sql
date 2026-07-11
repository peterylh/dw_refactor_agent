-- Deterministic smoke data for Fineract acc_product_mapping
TRUNCATE TABLE retail_banking_dm.ods_fineract_acc_product_mapping;

INSERT INTO retail_banking_dm.ods_fineract_acc_product_mapping (
    `id`,
    `gl_account_id`,
    `product_id`,
    `product_type`,
    `payment_type`,
    `charge_id`,
    `financial_account_type`,
    `charge_off_reason_id`,
    `capitalized_income_classification_id`,
    `buydown_fee_classification_id`,
    `write_off_reason_id`,
    `load_time`
) VALUES
    (
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        1,
        '2025-01-15 00:00:00'
    );
