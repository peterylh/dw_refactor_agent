"""
Core repository and runtime configuration.
"""

from __future__ import annotations

from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TEXT_ENCODING = "utf-8"

# Stable layer order for dependency checks and display sorting. Table layer
# ownership comes from model YAML, not table-name prefixes.
LAYER_ORDER = [
    ["ODS"],
    ["DIM", "DWD"],
    ["DWS"],
    ["ADS"],
]


# Each data mart project has one default catalog and two Doris databases:
#   catalog - default catalog, internal when omitted
#   db      - production database used by ETL and verification sources
#   qa_db   - validation database used by refactor shadow runs
#   ods_source_catalog_dialects - ODS source catalog to DDL dialect mapping
PROJECT_CONFIG = {
    "shop": {
        "dir": "shop",
        "catalog": "internal",
        "db": "shop_dm",
        "qa_db": "shop_dm_qa",
        "lineage_db": "shop_lineage",
        "naming_config": "shop/naming_config.yaml",
        "ods_source_catalog_dialects": {
            "internal": "doris",
        },
    },
    "finance_analytics": {
        "dir": "finance_analytics",
        "catalog": "internal",
        "db": "finance_analytics_dm",
        "qa_db": "finance_analytics_dm_qa",
        "lineage_db": "finance_analytics_lineage",
        "naming_config": "finance_analytics/naming_config.yaml",
        "ods_source_catalog_dialects": {
            "internal": "doris",
        },
    },
}

PROJECT_MAP = PROJECT_CONFIG


# Database environment configuration for the MySQL protocol.
DB_ENV_CONFIG = {
    "prod": {
        "host": "172.16.0.90",
        "port": 19030,
        "user": "root",
        "qa_user": "qa",
    },
    "test": {
        "host": "172.16.0.90",
        "port": 9034,
        "user": "root",
        "qa_user": "qa",
    },
}

# Doris HTTP protocol configuration, used by Stream Load.
DORIS_HTTP_PORT = 8030

# Default prod shortcuts.
DORIS_HOST = DB_ENV_CONFIG["prod"]["host"]
DORIS_PORT = DB_ENV_CONFIG["prod"]["port"]
DORIS_USER = DB_ENV_CONFIG["prod"]["user"]
DORIS_QA_USER = DB_ENV_CONFIG["prod"]["qa_user"]


def get_mysql_cmd(env: str = "prod", qa: bool = False) -> list[str]:
    """Return mysql command-line arguments for a configured environment."""
    cfg = DB_ENV_CONFIG[env]
    user = cfg["qa_user"] if qa else cfg["user"]
    return ["mysql", f"-h{cfg['host']}", f"-P{cfg['port']}", f"-u{user}"]
