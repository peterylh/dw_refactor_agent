-- Deterministic smoke data for Fineract m_savings_product_charge
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_savings_product_charge;

INSERT INTO retail_banking_dm.ods_fineract_m_savings_product_charge (
    `savings_product_id`,
    `charge_id`,
    `load_time`
) VALUES
    (
        1,
        1,
        '2025-01-15 00:00:00'
    );
