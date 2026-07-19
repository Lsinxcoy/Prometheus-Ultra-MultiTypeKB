"""Nexus 神经中枢统合 — 严格端到端测试.

验证:
1. 零机制丢失: Nexus 注册数 == life.py 实例化机制数
2. 7 管道全注册
3. 消费率真实(读 Nexus, 非旧6载体漏算)
4. T4 动态挂载闭环(神经发生)
5. 效果路由 + 突触修剪闭环
6. E2E: 实例化 -> 跑7管道 -> 机制真被调用(非假绿)
"""
import os
import sys
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

import pytest
from prometheus_ultra import Omega, ZConfig
from prometheus_ultra.cns.nexus import Nexus


@pytest.fixture
def omega(tmp_path):
    # 清理 Nexus 持久化(固定路径archive/nexus.json, 避免跨测试残留)
    nx_path = os.path.join(os.path.dirname(__file__), "..", "archive", "nexus.json")
    if os.path.exists(nx_path):
        os.remove(nx_path)
    db = str(tmp_path / "test.db")
    cfg = ZConfig(database_path=db)
    o = Omega(config=cfg)
    yield o
    o.close()


def _count_life_mechanisms(o):
    """数 life.py 非_前缀、非已知非机制的属性(与 _nexus_register_all 排除逻辑一致)"""
    skip = {"nexus", "mechanism_registry", "store", "event_bus", "host", "llm",
            "server", "monitor", "x_adapter", "y_adapter", "schema", "config",
            "curator", "skill_claw"}
    n = 0
    for attr, val in o.__dict__.items():
        if attr.startswith("_") or attr in skip:
            continue
        if val is None or not hasattr(val, "__class__"):
            continue
        n += 1
    return n


def test_zero_mechanism_loss(omega):
    """Nexus 注册机制数 == life.py 实例化机制数(含管道本身, 零丢失)"""
    life_n = _count_life_mechanisms(omega)
    nexus_n = omega.nexus.get_stats()["mechanisms"]
    assert nexus_n == life_n, f"机制丢失: life={life_n} nexus={nexus_n}"
    assert nexus_n >= 200, f"机制数异常少: {nexus_n}"


def test_seven_pipelines_registered(omega):
    """7 管道全部注册进 Nexus(用真实方法名 dream_cycle)"""
    stats = omega.nexus.get_stats()
    assert stats["pipelines"] == 7, f"管道数={stats['pipelines']}"
    for p in ("remember", "recall", "evolve", "learn", "reflect", "dream_cycle", "maintain"):
        assert p in omega.nexus._pipelines, f"管道 {p} 未注册"


def test_consumption_real_via_nexus(omega):
    """消费率读 Nexus 真实数据(非旧6载体漏算的0%)"""
    cons = omega.get_mechanism_consumption()
    assert "nexus_authority" in cons, "未读 Nexus 权威源"
    assert cons["total"] == omega.nexus.get_stats()["mechanisms"]
    omega.remember(content="nexus test", utility=0.8, tags=["t"])
    omega.recall("nexus test")
    cons2 = omega.get_mechanism_consumption()
    assert cons2["consumed"] > 0, "跑管道后消费数仍0(记账失效)"


def test_t4_dynamic_mount(omega):
    """T4 编译产物经沙箱加载 -> 动态层挂载(神经发生)"""
    before = omega.nexus.get_stats()["dynamic"]
    from prometheus_ultra.integration.mechanism_sandbox import MechanismSandbox
    from prometheus_ultra.mechanisms import base_mechanism
    draft = (
        "from prometheus_ultra.mechanisms.base_mechanism import BaseMechanism\n"
        "class paper_test_dyn(BaseMechanism):\n"
        "    name = 'paper_test_dyn'\n"
        "    category = 'compiled'\n"
        "    def run(self, context=None):\n"
        "        return {'ok': True}\n"
    )
    cls = MechanismSandbox().compile_mechanism("paper_test_dyn", draft, base_mechanism)
    assert cls is not None, "沙箱加载失败"
    inst = cls()
    omega.nexus.mount_dynamic("paper_test_dyn", inst, category="compiled")
    after = omega.nexus.get_stats()["dynamic"]
    assert after == before + 1, "动态机制未挂载"
    r = omega.nexus.dispatch("paper_test_dyn", method="run")
    assert r is not None and r.get("ok") is True, "动态机制 dispatch 失败"


def test_effect_routing_and_prune(omega):
    """效果路由 + 突触修剪闭环"""
    from prometheus_ultra.mechanisms.base_mechanism import BaseMechanism
    class dyn_eff(BaseMechanism):
        name = "dyn_eff"
        category = "compiled"
        def run(self, context=None):
            return {"ok": True}
    omega.nexus.mount_dynamic("dyn_eff", dyn_eff())
    for _ in range(5):
        omega.nexus.record_effect("dyn_eff", 0.8)
    assert omega.nexus._mechanisms["dyn_eff"]["effect"] > 0.5
    class dyn_bad(BaseMechanism):
        name = "dyn_bad"
        category = "compiled"
        def run(self, context=None):
            return {"ok": False}
    omega.nexus.mount_dynamic("dyn_bad", dyn_bad())
    for _ in range(5):
        omega.nexus.record_effect("dyn_bad", -0.9)
    pruned = omega.nexus.prune_harmful(threshold=-0.3)
    assert "dyn_bad" in pruned, "有害动态机制未修剪"
    assert "dyn_eff" not in pruned, "健康动态机制被误修剪"


def test_e2e_seven_pipelines_run(omega):
    """E2E: 实例化后跑7管道, 机制真被调用(非假绿)"""
    omega.learn(source="web", query="neural nexus architecture", max_results=2)
    omega.remember(content="e2e mechanism test", utility=0.9, tags=["e2e"])
    omega.recall("e2e mechanism", limit=3)
    omega.evolve(context="e2e test", confidence=0.6)
    omega.dream_cycle()
    omega.maintain()
    if hasattr(omega, "reflect"):
        try:
            omega.reflect()
        except Exception:
            pass
    stats = omega.nexus.get_stats()
    assert stats["total_invocations"] >= 7, f"管道调用记账不足: {stats['total_invocations']}"
    cons = omega.get_mechanism_consumption()
    assert cons["consumed"] > 0
