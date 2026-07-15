"""Git 模式测试: 验证 derive_from_git 及其辅助函数。"""

import subprocess
from pathlib import Path

from dw_refactor_agent.ddl_deriver.ddl_deriver import (
    AlterTable,
    CreateTable,
    RenameTable,
    _find_git_root,
    derive_from_git,
)

# ============================================================
# 工具: 构造测试用 git repo
# ============================================================

DDL_USER_OLD = """DROP TABLE IF EXISTS shop_dm.ods_user_info;
CREATE TABLE IF NOT EXISTS shop_dm.ods_user_info (
    id     BIGINT       NOT NULL COMMENT 'ID',
    name   VARCHAR(64)  NOT NULL COMMENT '姓名',
    age    INT          NULL COMMENT '年龄',
    phone  VARCHAR(20)  NULL COMMENT '手机号'
) ENGINE=OLAP DUPLICATE KEY(id) DISTRIBUTED BY HASH(id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
"""

DDL_USER_NEW = """DROP TABLE IF EXISTS shop_dm.ods_customer;
CREATE TABLE IF NOT EXISTS shop_dm.ods_customer (
    id       BIGINT       NOT NULL COMMENT 'ID',
    name     VARCHAR(64)  NOT NULL COMMENT '姓名',
    age      INT          NULL COMMENT '年龄',
    phone    VARCHAR(20)  NULL COMMENT '手机号',
    address  VARCHAR(256) NULL COMMENT '地址'
) ENGINE=OLAP DUPLICATE KEY(id) DISTRIBUTED BY HASH(id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
"""

DDL_ORDER = """DROP TABLE IF EXISTS shop_dm.ods_order;
CREATE TABLE IF NOT EXISTS shop_dm.ods_order (
    order_id     BIGINT        NOT NULL COMMENT '订单ID',
    total_amount DECIMAL(12,2) NOT NULL COMMENT '订单总额'
) ENGINE=OLAP DUPLICATE KEY(order_id) DISTRIBUTED BY HASH(order_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
"""

DDL_ORDER_MODIFIED = """DROP TABLE IF EXISTS shop_dm.ods_order;
CREATE TABLE IF NOT EXISTS shop_dm.ods_order (
    order_id     BIGINT        NOT NULL COMMENT '订单ID',
    total_amount DECIMAL(14,2) NOT NULL COMMENT '订单总额'
) ENGINE=OLAP DUPLICATE KEY(order_id) DISTRIBUTED BY HASH(order_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
"""

DDL_DIR_REL = "unit_project/ddl"


def _git(repo: Path, *args: str) -> str:
    return subprocess.run(
        ["git", "-C", str(repo), *args],
        capture_output=True,
        text=True,
        check=True,
        timeout=15,
    ).stdout.strip()


def _init_test_repo(tmp_path: Path) -> Path:
    """创建测试用 git repo, 返回 repo 根目录.

    初始结构:
      unit_project/ddl/ods_user_info.sql  (4 列)
      unit_project/ddl/ods_order.sql      (2 列)
    """
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "test")

    ddl_dir = repo / DDL_DIR_REL
    ddl_dir.mkdir(parents=True)
    (ddl_dir / "ods_user_info.sql").write_text(DDL_USER_OLD)
    (ddl_dir / "ods_order.sql").write_text(DDL_ORDER)

    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "initial commit")
    _git(repo, "branch", "-M", "main")
    return repo


# ============================================================
# 测试 _find_git_root
# ============================================================


def test_find_git_root(tmp_path):
    repo = _init_test_repo(tmp_path)
    found = _find_git_root(repo / DDL_DIR_REL)
    assert found.resolve() == repo.resolve()


def test_find_git_root_fails(tmp_path):
    import pytest

    with pytest.raises(FileNotFoundError):
        _find_git_root(tmp_path)


# ============================================================
# 测试 _get_merge_base
# ============================================================


# ============================================================
# 测试 Git ref DDL 读取
# ============================================================


# ============================================================
# 测试 derive_from_git
# ============================================================


def test_git_default_project_scans_split_mart_ddl_dirs(tmp_path):
    """默认 git 模式覆盖项目 mid/ddl 与 ads/ddl."""
    repo = tmp_path / "repo"
    repo.mkdir(parents=True)
    _git(repo, "init")
    _git(repo, "config", "user.email", "test@test.com")
    _git(repo, "config", "user.name", "test")

    mid_ddl = repo / "warehouses" / "shop" / "mid" / "ddl"
    ads_ddl = repo / "warehouses" / "shop" / "ads" / "ddl"
    mid_ddl.mkdir(parents=True)
    ads_ddl.mkdir(parents=True)
    (mid_ddl / "dwd_order.sql").write_text(
        DDL_ORDER.replace("ods_order", "dwd_order")
    )

    _git(repo, "add", "-A")
    _git(repo, "commit", "-m", "initial commit")
    _git(repo, "branch", "-M", "main")

    (mid_ddl / "dwd_order.sql").write_text(
        DDL_ORDER_MODIFIED.replace("ods_order", "dwd_order")
    )
    (ads_ddl / "ads_order_summary.sql").write_text(
        """DROP TABLE IF EXISTS shop_dm.ads_order_summary;
CREATE TABLE IF NOT EXISTS shop_dm.ads_order_summary (
    order_date DATE NOT NULL COMMENT '日期',
    order_count BIGINT NULL COMMENT '订单数'
) ENGINE=OLAP DUPLICATE KEY(order_date) DISTRIBUTED BY HASH(order_date) BUCKETS 10
PROPERTIES ("replication_num" = "1");
"""
    )

    changes = derive_from_git(repo=repo)

    assert {change.change_type for change in changes} == {"ALTER", "CREATE"}
    assert any(
        isinstance(change, AlterTable)
        and change.table_name == "shop_dm.dwd_order"
        for change in changes
    )
    assert any(
        isinstance(change, CreateTable)
        and change.table_def.short_name == "ads_order_summary"
        for change in changes
    )


def test_git_rename_add_column(tmp_path):
    """重命名 + 新增列 → RENAME + ALTER."""
    repo = _init_test_repo(tmp_path)

    # 在工作区修改: 删除 ods_user_info.sql, 新增 ods_customer.sql (5 列)
    ddl_dir = repo / DDL_DIR_REL
    (ddl_dir / "ods_user_info.sql").unlink()
    (ddl_dir / "ods_customer.sql").write_text(DDL_USER_NEW)

    changes = derive_from_git(ddl_dir_rel=DDL_DIR_REL, repo=repo)
    assert len(changes) == 2
    assert isinstance(changes[0], RenameTable)
    assert changes[0].old_short == "ods_user_info"
    assert changes[0].new_short == "ods_customer"
    assert isinstance(changes[1], AlterTable)
    assert changes[1].table_name == "shop_dm.ods_customer"
    assert len(changes[1].adds) == 1
    assert changes[1].adds[0].name == "address"


def test_git_mixed_changes(tmp_path):
    """批量: 重命名 + 修改 + 新增 + 删除."""
    repo = _init_test_repo(tmp_path)
    ddl_dir = repo / DDL_DIR_REL

    # rename: ods_user_info -> ods_customer (+ address)
    (ddl_dir / "ods_user_info.sql").unlink()
    (ddl_dir / "ods_customer.sql").write_text(DDL_USER_NEW)

    # alter: ods_order total_amount DECIMAL(12,2) -> DECIMAL(14,2)
    (ddl_dir / "ods_order.sql").write_text(DDL_ORDER_MODIFIED)

    # create: ods_feedback
    (
        ddl_dir / "ods_feedback.sql"
    ).write_text("""DROP TABLE IF EXISTS shop_dm.ods_feedback;
CREATE TABLE IF NOT EXISTS shop_dm.ods_feedback (
    feedback_id BIGINT NOT NULL COMMENT '反馈ID'
) ENGINE=OLAP DUPLICATE KEY(feedback_id) DISTRIBUTED BY HASH(feedback_id) BUCKETS 10
PROPERTIES ("replication_num" = "1");
""")

    changes = derive_from_git(ddl_dir_rel=DDL_DIR_REL, repo=repo)
    types = {c.change_type for c in changes}
    assert types == {"RENAME", "ALTER", "CREATE"}
    assert sum(1 for c in changes if c.change_type == "RENAME") == 1
    assert sum(1 for c in changes if c.change_type == "ALTER") >= 1
    assert sum(1 for c in changes if c.change_type == "CREATE") == 1
