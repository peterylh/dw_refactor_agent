SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.bridge_product_gl_mapping
TRUNCATE TABLE retail_banking_dm.bridge_product_gl_mapping;

INSERT INTO retail_banking_dm.bridge_product_gl_mapping (
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
    `etl_time`
)
SELECT
    src.`id`,
    src.`gl_account_id`,
    src.`product_id`,
    src.`product_type`,
    src.`payment_type`,
    src.`charge_id`,
    src.`financial_account_type`,
    src.`charge_off_reason_id`,
    src.`capitalized_income_classification_id`,
    src.`buydown_fee_classification_id`,
    src.`write_off_reason_id`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_acc_product_mapping AS src;
