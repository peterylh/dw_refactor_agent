SET @etl_date = COALESCE(@etl_date, CURDATE());

-- Human-reviewed semantic target: retail_banking_dm.dwd_standing_instruction_event
TRUNCATE TABLE retail_banking_dm.dwd_standing_instruction_event;

INSERT INTO retail_banking_dm.dwd_standing_instruction_event (
    `id`,
    `standing_instruction_id`,
    `status`,
    `execution_time`,
    `amount`,
    `error_log`,
    `business_date`,
    `etl_time`
)
SELECT
    src.`id`,
    src.`standing_instruction_id`,
    src.`status`,
    src.`execution_time`,
    src.`amount`,
    src.`error_log`,
    DATE(src.`execution_time`) AS `business_date`,
    CURRENT_TIMESTAMP AS `etl_time`
FROM retail_banking_dm.ods_fineract_m_account_transfer_standing_instructions_history AS src;
