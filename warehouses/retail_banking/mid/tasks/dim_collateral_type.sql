-- Human-reviewed semantic target: retail_banking_dm.dim_collateral_type
TRUNCATE TABLE retail_banking_dm.dim_collateral_type;

INSERT INTO retail_banking_dm.dim_collateral_type (
    `id`,
    `name`,
    `quality`,
    `base_price`,
    `unit_type`,
    `pct_to_base`,
    `currency`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`name`,
    src.`quality`,
    src.`base_price`,
    src.`unit_type`,
    src.`pct_to_base`,
    src.`currency`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_collateral_management AS src;
