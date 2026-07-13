-- Deterministic smoke data for Fineract m_address
TRUNCATE TABLE retail_banking_dm.ods_fineract_m_address;

INSERT INTO retail_banking_dm.ods_fineract_m_address (
    `id`,
    `street`,
    `address_line_1`,
    `address_line_2`,
    `address_line_3`,
    `town_village`,
    `city`,
    `county_district`,
    `state_province_id`,
    `country_id`,
    `postal_code`,
    `latitude`,
    `longitude`,
    `created_by`,
    `created_on`,
    `updated_by`,
    `updated_on`,
    `load_time`
) VALUES
    (
        1,
        'm_address_street_1',
        'm_address_address_line_1_1',
        'm_address_address_line_2_1',
        'm_address_address_line_3_1',
        'm_address_town_village_1',
        'm_address_city_1',
        'm_address_county_district_1',
        1,
        1,
        'm_address_',
        1,
        1,
        'm_address_created_by_1',
        '2025-01-15',
        'm_address_updated_by_1',
        '2025-01-15',
        '2025-01-15 00:00:00'
    );
