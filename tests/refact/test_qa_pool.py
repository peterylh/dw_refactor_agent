from __future__ import annotations

import pytest

from dw_refactor_agent.refactor.qa_pool import configured_qa_pool


def _project_config(pool=None):
    verification = {}
    if pool is not None:
        verification["qa_database_pool"] = pool
    return {
        "db": "shop_dm",
        "qa_db": "shop_dm_qa",
        "lineage_db": "shop_lineage",
        "verification": verification,
    }


def test_configured_qa_pool_normalizes_explicit_pool():
    assert configured_qa_pool(
        "shop",
        _project_config(["shop_dm_qa", "shop_dm_qa_02"]),
    ) == ("shop_dm_qa", "shop_dm_qa_02")


def test_configured_qa_pool_falls_back_to_legacy_qa_database():
    assert configured_qa_pool("shop", _project_config()) == ("shop_dm_qa",)


@pytest.mark.parametrize(
    "pool, expected",
    [
        ([], "non-empty"),
        (["shop_dm"], "production database"),
        (["shop_lineage"], "lineage database"),
        (["bad-name"], "identifier"),
        (["shop_dm_qa", "SHOP_DM_QA"], "duplicate"),
        (["information_schema"], "system database"),
    ],
)
def test_configured_qa_pool_rejects_unsafe_values(pool, expected):
    with pytest.raises(ValueError, match=expected):
        configured_qa_pool("shop", _project_config(pool))
