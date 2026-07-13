-- Deterministic smoke data for Fineract oauth_client_details
TRUNCATE TABLE retail_banking_dm.ods_fineract_oauth_client_details;

INSERT INTO retail_banking_dm.ods_fineract_oauth_client_details (
    `client_id`,
    `resource_ids`,
    `client_secret`,
    `scope`,
    `authorized_grant_types`,
    `web_server_redirect_uri`,
    `authorities`,
    `access_token_validity`,
    `refresh_token_validity`,
    `additional_information`,
    `autoapprove`,
    `load_time`
) VALUES
    (
        'oauth_client_details_client_id_1',
        'oauth_client_details_resource_ids_1',
        'SYNTHETIC_REDACTED',
        'oauth_client_details_scope_1',
        'oauth_client_details_authorized_grant_types_1',
        'oauth_client_details_web_server_redirect_uri_1',
        'oauth_client_details_authorities_1',
        1,
        1,
        'oauth_client_details_additional_information_1',
        FALSE,
        '2025-01-15 00:00:00'
    );
