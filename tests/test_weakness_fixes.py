"""薄弱点修复回归测试。

覆盖:
- host_agent._mark_consumed: 机制消费后沉淀 consumed_at 进 registry (B1 消费率维度从死变活)
- life._compute_fitness: 三维(multitype/consumption/rumination) 正确计入总分
"""
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from prometheus_ultra.integration.host_agent import GenericAgentAdapter, HostAgentAdapter
from prometheus_ultra.life import Omega
from prometheus_ultra.foundation.schema import NodeType


def test_mark_consumed_writes_registry():
    """_mark_consumed 把 consumed_at 写进 registry._mechanisms[name]。"""
    reg = type("R", (), {"_mechanisms": {"m1": {"status": "active"}}})()
    omega = type("O", (), {"mechanism_registry": reg})()
    ad = GenericAgentAdapter(host_id="test")
    ad._omega = omega

    ad._mark_consumed("m1")

    assert reg._mechanisms["m1"].get("consumed_at") is not None
    # 不存在的 name 不崩
    ad._mark_consumed("nonexistent")


def test_mark_consumed_no_omega_is_safe():
    """无 _omega 反向持有时静默跳过, 不崩。"""
    ad = GenericAgentAdapter(host_id="test")
    ad._mark_consumed("m1")  # 无 _omega -> 静默


def test_compute_fitness_includes_new_dimensions():
    """_compute_fitness 返回 [0,1] 且 _last_fitness_detail 含三维。"""
    o = Omega(db_path="src/prometheus_ultra.db")
    total = o._compute_fitness()
    assert isinstance(total, float)
    assert 0.0 <= total <= 1.0
    detail = getattr(o, "_last_fitness_detail", {})
    assert "multitype" in detail
    assert "consumption" in detail
    assert "rumination" in detail
    # 三维各自封顶 0.1
    for k in ("multitype", "consumption", "rumination"):
        assert 0.0 <= detail[k] <= 0.1, f"{k}={detail[k]} 超范围"
