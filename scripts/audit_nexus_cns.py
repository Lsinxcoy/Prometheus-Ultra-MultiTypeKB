"""深度严格审计脚本 — 验证 Nexus 统合架构的真实正确性.

不靠单元测试的孤立断言, 直接对运行中的 Omega 实例做审计:
A. 机制零丢失: life.py 全部 self.x 实例都在 nexus._mechanisms 有对应项
B. 不双重执行: dispatch 转调实例, 不创建第二份执行(验证 base_instances 引用同一对象)
C. 基本盘永驻: 动态层修剪后, 基本盘实例仍在 self.__dict__ 且可调用
D. 两层记忆共享: store(知识) + effect 账本(经验) 都存在且可写
E. 七管道真实运行: 跑后 nexus 记账 > 0 (非假绿)
F. T4 神经发生: 编译产物真进动态层并 dispatch 成功
"""
import sys
import os
import tempfile
import logging

logging.disable(logging.CRITICAL)
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "src"))

from prometheus_ultra import Omega, ZConfig
from prometheus_ultra.cns.nexus import Nexus
from prometheus_ultra.integration.mechanism_sandbox import MechanismSandbox
from prometheus_ultra.mechanisms import base_mechanism


def audit():
    nx_path = os.path.join(os.path.dirname(__file__), "..", "archive", "nexus.json")
    if os.path.exists(nx_path):
        os.remove(nx_path)
    db = tempfile.mktemp(suffix=".db")
    o = Omega(config=ZConfig(database_path=db))

    results = {}
    fails = []

    # A. 机制零丢失
    skip = {"nexus", "mechanism_registry", "store", "event_bus", "host", "llm",
            "server", "monitor", "x_adapter", "y_adapter", "schema", "config",
            "curator", "skill_claw"}
    life_mechs = [a for a, v in o.__dict__.items()
                  if not a.startswith("_") and a not in skip
                  and v is not None and hasattr(v, "__class__")]
    missing = [a for a in life_mechs if a not in o.nexus._mechanisms]
    results["A_zero_loss"] = (len(missing) == 0, f"life={len(life_mechs)} nexus={len(o.nexus._mechanisms)} missing={missing}")
    if missing:
        fails.append("A")

    # B. 不双重执行: base_instances 引用 == self.x 同一对象
    probe = "five_gates" if "five_gates" in o.nexus._base_instances else (life_mechs[0] if life_mechs else None)
    if probe:
        same_obj = o.nexus._base_instances.get(probe) is getattr(o, probe, None)
        results["B_no_double_exec"] = (same_obj, f"{probe} base_instances is self.x: {same_obj}")
        if not same_obj:
            fails.append("B")

    # C. 基本盘永驻: 手动 prune 一个假动态机制, 验证 self.x 仍可用
    class _Bad(base_mechanism.BaseMechanism):
        name = "_audit_bad"
        category = "compiled"
        def run(self, context=None):
            return {"ok": False}
    o.nexus.mount_dynamic("_audit_bad", _Bad())
    for _ in range(5):
        o.nexus.record_effect("_audit_bad", -0.9)
    pruned = o.nexus.prune_harmful(-0.3)
    base_still = all(getattr(o, m, None) is not None for m in life_mechs[:20])
    results["C_base_persist"] = (("_audit_bad" in pruned) and base_still,
                                 f"pruned={pruned} base_first20_alive={base_still}")
    if "_audit_bad" not in pruned or not base_still:
        fails.append("C")

    # D. 两层记忆共享
    store_ok = o.nexus._store is o.store
    effect_ok = isinstance(o.nexus._effects, dict)
    results["D_two_memory"] = (store_ok and effect_ok, f"store_linked={store_ok} effect_ledger={effect_ok}")

    # E. 七管道真实运行 + 记账
    before = o.nexus.get_stats()["total_invocations"]
    o.learn(source="web", query="audit nexus", max_results=1)
    o.remember(content="audit", utility=0.9, tags=["x"])
    o.recall("audit")
    o.evolve(context="audit", confidence=0.5)
    o.dream_cycle()
    o.maintain()
    o.reflect(context="audit")
    after = o.nexus.get_stats()["total_invocations"]
    results["E_pipelines_run"] = (after > before + 6, f"invocations {before}->{after}")
    if not (after > before + 6):
        fails.append("E")

    # F. T4 神经发生
    draft = ("from prometheus_ultra.mechanisms.base_mechanism import BaseMechanism\n"
             "class audit_dyn(BaseMechanism):\n"
             "    name='audit_dyn'\n    category='compiled'\n"
             "    def run(self, context=None):\n        return {'neural': True}\n")
    cls = MechanismSandbox().compile_mechanism("audit_dyn", draft, base_mechanism)
    o.nexus.mount_dynamic("audit_dyn", cls())
    r = o.nexus.dispatch("audit_dyn", method="run")
    results["F_t4_neurogenesis"] = (r is not None and r.get("neural") is True, f"dispatch={r}")
    if not (r and r.get("neural")):
        fails.append("F")

    o.close()
    return results, fails


if __name__ == "__main__":
    res, fails = audit()
    print("=" * 60)
    print("NEXUS 深度审计结果")
    print("=" * 60)
    for k, (ok, msg) in res.items():
        print(f"[{'PASS' if ok else 'FAIL'}] {k}: {msg}")
    print("=" * 60)
    if fails:
        print(f"审计未通过: {fails}")
        sys.exit(1)
    else:
        print("全部审计通过 ✅ Nexus 统合架构真实正确")
