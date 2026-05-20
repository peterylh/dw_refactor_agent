import json

import pytest

from lineage.job_dag import JobDAG

# ============================================================
# Helper: 快速构造边列表
# ============================================================

def _edges(*pairs):
    """(src, tgt) → [{"source": "src.col", "target": "tgt.col"}]"""
    return [{"source": f"{s}.x", "target": f"{t}.x"} for s, t in pairs]


# ============================================================
# 1. 初始化 & 图构建
# ============================================================


def test_init_empty():
    dag = JobDAG()
    assert dag._edges == []
    assert dag._deps == {}
    assert dag._rev == {}


def test_init_empty_edges():
    dag = JobDAG([])
    assert dag._deps == {}
    assert dag._rev == {}


def test_init_single_edge():
    dag = JobDAG(_edges(("a", "b")))
    assert dag._deps == {"a": {"b"}}
    assert dag._rev == {"b": {"a"}}


def test_init_chain():
    dag = JobDAG(_edges(("a", "b"), ("b", "c")))
    assert dag._deps == {"a": {"b"}, "b": {"c"}}
    assert dag._rev == {"b": {"a"}, "c": {"b"}}


def test_init_self_reference():
    """自引用边 (a→a) 应被忽略."""
    dag = JobDAG(_edges(("a", "a")))
    assert dag._deps == {}
    assert dag._rev == {}


def test_init_self_and_normal():
    dag = JobDAG(_edges(("a", "a"), ("a", "b")))
    assert dag._deps == {"a": {"b"}}
    assert dag._rev == {"b": {"a"}}


def test_init_multi_targets():
    """一个源表流向多个目标表."""
    dag = JobDAG(_edges(("a", "b"), ("a", "c")))
    assert dag._deps == {"a": {"b", "c"}}
    assert dag._rev == {"b": {"a"}, "c": {"a"}}


def test_init_multi_sources():
    """多个源表流向一个目标表."""
    dag = JobDAG(_edges(("a", "c"), ("b", "c")))
    assert dag._deps == {"a": {"c"}, "b": {"c"}}
    assert dag._rev == {"c": {"a", "b"}}


# ============================================================
# 2. add_edge
# ============================================================


def test_add_edge():
    dag = JobDAG()
    dag.add_edge("a", "b")
    assert dag._deps == {"a": {"b"}}
    assert dag._rev == {"b": {"a"}}
    assert {"source": "a", "target": "b"} in dag._edges


def test_add_edge_self_reference():
    """自引用 add_edge 不添加."""
    dag = JobDAG(_edges(("a", "b")))
    dag.add_edge("a", "a")
    assert dag._deps == {"a": {"b"}}


def test_add_edge_multiple():
    dag = JobDAG()
    dag.add_edge("a", "b")
    dag.add_edge("a", "c")
    assert dag._deps["a"] == {"b", "c"}


# ============================================================
# 3. bfs_downstream  (从 test_analyze_refact.py 迁移 + 增强)
# ============================================================


def test_bfs_downstream_empty():
    dag = JobDAG()
    assert dag.bfs_downstream({"t1"}) == set()


def test_bfs_downstream_empty_seeds():
    dag = JobDAG(_edges(("a", "b")))
    assert dag.bfs_downstream(set()) == set()


def test_bfs_downstream_single_hop():
    dag = JobDAG(_edges(("a", "b")))
    assert dag.bfs_downstream({"a"}) == {"b"}


def test_bfs_downstream_multi_hop():
    dag = JobDAG(_edges(("a", "b"), ("b", "c")))
    result = dag.bfs_downstream({"a"})
    assert result == {"b", "c"}


def test_bfs_downstream_branching():
    dag = JobDAG(_edges(("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")))
    result = dag.bfs_downstream({"a"})
    assert result == {"b", "c", "d"}


def test_bfs_downstream_cycle():
    """环不应导致无限循环."""
    dag = JobDAG(_edges(("a", "b"), ("b", "c"), ("c", "a")))
    result = dag.bfs_downstream({"a"})
    assert result == {"b", "c"}


def test_bfs_downstream_multiple_seeds():
    dag = JobDAG(_edges(("a", "b"), ("c", "d")))
    result = dag.bfs_downstream({"a", "c"})
    assert result == {"b", "d"}


def test_bfs_downstream_no_downstream():
    """当种子没有下游时返回空."""
    dag = JobDAG(_edges(("a", "b")))
    assert dag.bfs_downstream({"c"}) == set()


def test_bfs_downstream_deep_chain():
    dag = JobDAG(_edges(("a", "b"), ("b", "c"), ("c", "d"), ("d", "e")))
    result = dag.bfs_downstream({"a"})
    assert result == {"b", "c", "d", "e"}


def test_bfs_downstream_partial_graph():
    dag = JobDAG(_edges(("a", "b"), ("b", "c"), ("d", "e")))
    result = dag.bfs_downstream({"a"})
    assert result == {"b", "c"}


# ============================================================
# 4. topological_sort
# ============================================================


def test_topological_sort_empty():
    dag = JobDAG()
    assert dag.topological_sort(set()) == []


def test_topological_sort_single():
    dag = JobDAG()
    assert dag.topological_sort({"a"}) == ["a"]


def test_topological_sort_linear_chain():
    dag = JobDAG(_edges(("a", "b"), ("b", "c")))
    result = dag.topological_sort({"a", "b", "c"})
    assert result == ["a", "b", "c"]


def test_topological_sort_branching():
    """a → b, a → c, b → d, c → d → a 在最前, d 在最后, b/c 任意."""
    dag = JobDAG(_edges(("a", "b"), ("a", "c"), ("b", "d"), ("c", "d")))
    result = dag.topological_sort({"a", "b", "c", "d"})
    assert result[0] == "a"
    assert result[-1] == "d"
    assert set(result[1:3]) == {"b", "c"}
    assert len(result) == 4


def test_topological_sort_parallel_chains():
    """a→b, c→d → 两条独立链路, 输出顺序任意但依赖关系必须保持."""
    dag = JobDAG(_edges(("a", "b"), ("c", "d")))
    result = dag.topological_sort({"a", "b", "c", "d"})
    assert len(result) == 4
    # a 在 b 之前, c 在 d 之前
    assert result.index("a") < result.index("b")
    assert result.index("c") < result.index("d")


def test_topological_sort_filtered_edges():
    """edges 中包含不在 jobs_set 的表, 应被忽略."""
    dag = JobDAG(_edges(("a", "b"), ("b", "c"), ("x", "y")))
    result = dag.topological_sort({"a", "b", "c"})
    assert result == ["a", "b", "c"]


def test_topological_sort_cycle_raises():
    dag = JobDAG(_edges(("a", "b"), ("b", "c"), ("c", "a")))
    with pytest.raises(ValueError, match="cycle"):
        dag.topological_sort({"a", "b", "c"})


def test_topological_sort_partial_cycle():
    """环只涉及部分节点, 其他正常节点也应报错.""" 
    dag = JobDAG(_edges(("a", "b"), ("b", "c"), ("c", "a"), ("d", "e")))
    with pytest.raises(ValueError, match="cycle"):
        dag.topological_sort({"a", "b", "c"})


def test_topological_sort_self_reference():
    """自引用边 a→a 被忽略, 不影响拓扑排序."""
    dag = JobDAG(_edges(("a", "a"), ("a", "b")))
    result = dag.topological_sort({"a", "b"})
    assert result == ["a", "b"]


def test_topological_sort_preserves_all_jobs():
    dag = JobDAG(_edges(("a", "b"), ("b", "c")))
    result = dag.topological_sort({"a", "b", "c"})
    assert set(result) == {"a", "b", "c"}


def test_topological_sort_dependency_before_dependent():
    """每个依赖表在依赖者之前出现."""
    dag = JobDAG(_edges(("a", "b"), ("b", "c"), ("d", "c")))
    result = dag.topological_sort({"a", "b", "c", "d"})
    positions = {t: i for i, t in enumerate(result)}
    assert positions["a"] < positions["b"]
    assert positions["b"] < positions["c"]
    assert positions["d"] < positions["c"]


def test_topological_sort_no_edges():
    """无依赖边的作业, 以某种确定性顺序返回."""
    dag = JobDAG()
    result = dag.topological_sort({"a", "b", "c"})
    assert set(result) == {"a", "b", "c"}
    assert len(result) == 3


def test_topological_sort_unrelated_jobs():
    """jobs 中出现不在图中的表, 应作为无依赖节点排在前面."""
    dag = JobDAG(_edges(("a", "b")))
    result = dag.topological_sort({"a", "b", "x"})
    assert set(result) == {"a", "b", "x"}
    assert result.index("a") < result.index("b")


# ============================================================
# 5. 序列化
# ============================================================


def test_to_dict_from_dict_empty():
    dag = JobDAG()
    d = dag.to_dict()
    assert d == {"edges": [], "deps": {}, "rev": {}}
    dag2 = JobDAG.from_dict(d)
    assert dag2._edges == []
    assert dag2._deps == {}
    assert dag2._rev == {}


def test_to_dict_from_dict_roundtrip():
    edges = _edges(("a", "b"), ("b", "c"))
    dag = JobDAG(edges)
    d = dag.to_dict()
    assert "edges" in d
    assert "deps" in d
    assert "rev" in d
    # deps 和 rev 的 value 是 list (已排序)
    assert d["deps"]["a"] == ["b"]
    assert d["deps"]["b"] == ["c"]
    assert d["rev"]["b"] == ["a"]
    assert d["rev"]["c"] == ["b"]

    dag2 = JobDAG.from_dict(d)
    assert dag2._edges == edges
    assert dag2._deps == {"a": {"b"}, "b": {"c"}}
    assert dag2._rev == {"b": {"a"}, "c": {"b"}}


def test_to_dict_from_dict_bfs():
    """反序列化后 bfs_downstream 仍正常工作."""
    edges = _edges(("a", "b"), ("b", "c"))
    dag = JobDAG(edges)
    d = dag.to_dict()
    dag2 = JobDAG.from_dict(d)
    assert dag2.bfs_downstream({"a"}) == {"b", "c"}


def test_to_dict_from_dict_topological_sort():
    """反序列化后 topological_sort 仍正常工作."""
    edges = _edges(("a", "b"), ("b", "c"))
    dag = JobDAG(edges)
    d = dag.to_dict()
    dag2 = JobDAG.from_dict(d)
    assert dag2.topological_sort({"a", "b", "c"}) == ["a", "b", "c"]


def test_save_and_load(tmp_path):
    edges = _edges(("a", "b"))
    dag = JobDAG(edges)
    p = tmp_path / "dag.json"
    dag.save(p)
    assert p.exists()
    raw = json.loads(p.read_text())
    assert raw["edges"] == edges

    dag2 = JobDAG.load(p)
    assert dag2._edges == edges
    assert dag2._deps == {"a": {"b"}}
    assert dag2.bfs_downstream({"a"}) == {"b"}
    assert dag2.topological_sort({"a", "b"}) == ["a", "b"]


def test_save_load_empty(tmp_path):
    dag = JobDAG()
    p = tmp_path / "empty.json"
    dag.save(p)
    dag2 = JobDAG.load(p)
    assert dag2._edges == []


def test_save_load_custom_metadata(tmp_path):
    """保存加载后, add_edge 仍正常工作."""
    dag = JobDAG()
    p = tmp_path / "dag.json"
    dag.save(p)
    dag2 = JobDAG.load(p)
    dag2.add_edge("x", "y")
    assert dag2.bfs_downstream({"x"}) == {"y"}


# ============================================================
# 6. 集成测试
# ============================================================


def test_integration_complex():
    """模拟真实场景: 多层 DWD → DWS → ADS."""
    edges = _edges(
        ("dwd_order_detail", "dws_store_sales_daily"),
        ("dwd_order_detail", "dws_product_sales_daily"),
        ("dws_store_sales_daily", "ads_store_performance"),
        ("dws_store_sales_daily", "ads_sales_dashboard"),
        ("dws_product_sales_daily", "ads_sales_dashboard"),
    )
    dag = JobDAG(edges)

    # 全部作业排序
    all_jobs = {
        "dwd_order_detail",
        "dws_store_sales_daily",
        "dws_product_sales_daily",
        "ads_store_performance",
        "ads_sales_dashboard",
    }
    order = dag.topological_sort(all_jobs)
    assert len(order) == 5
    assert order[0] == "dwd_order_detail"
    assert order[-1] in ("ads_store_performance", "ads_sales_dashboard")

    # 只追踪部分
    downstream = dag.bfs_downstream({"dwd_order_detail"})
    assert downstream == {
        "dws_store_sales_daily",
        "dws_product_sales_daily",
        "ads_store_performance",
        "ads_sales_dashboard",
    }


def test_integration_dwd_only_chain():
    """DWD 互相关联的场景."""
    edges = _edges(
        ("dwd_customer", "dwd_order_detail"),
        ("dwd_product", "dwd_order_detail"),
        ("dwd_store", "dwd_order_detail"),
    )
    dag = JobDAG(edges)
    jobs = {"dwd_customer", "dwd_product", "dwd_store", "dwd_order_detail"}
    order = dag.topological_sort(jobs)
    # dwd_order_detail 必须在最后
    assert order[-1] == "dwd_order_detail"
    # 其他三个在顺序任意, 但都在 dwd_order_detail 之前
    for j in ("dwd_customer", "dwd_product", "dwd_store"):
        assert order.index(j) < order.index("dwd_order_detail")
