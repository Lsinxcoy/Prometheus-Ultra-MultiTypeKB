"""深度盘点 Ultra 系统内所有"机制/策略/模块" —— 按管道/模块逐层, 不限于注册表.

目标: 搞清楚系统到底有哪些机制, 散布在哪, 是否真被调用.
方法: 实例化 Omega, 内省其所有子系统属性 + 各模块导出的类/实例.
"""
import sys, os, inspect
sys.path.insert(0, "E:/Prometheus-Ultra-MultiTypeKB/src")
os.chdir("E:/Prometheus-Ultra-MultiTypeKB")

from prometheus_ultra.life import Omega

om = Omega(db_path="E:/Prometheus-Ultra-MultiTypeKB/src/prometheus_ultra.db")

print("=" * 70)
print("1) Omega 主对象直接持有的子系统(机制/策略/器官)")
print("=" * 70)
for attr in sorted(dir(om)):
    if attr.startswith("_"):
        continue
    try:
        v = getattr(om, attr)
    except Exception:
        continue
    if inspect.isroutine(v):
        continue
    # 只关注看起来是子系统/机制容器的属性
    tname = type(v).__name__
    mod = type(v).__module__
    if any(k in attr.lower() for k in ("registry", "engine", "harness", "gate", "manager",
                                        "loop", "bus", "store", "memory", "brain", "cortex",
                                        "regulator", "adapter", "bridge", "detector", "selector",
                                        "orchestrator", "pipeline", "handbook", "instinct",
                                        "evolution", "skill", "agent", "controller", "audit",
                                        "watchdog", "sentinel", "guard", "policy", "executor")):
        print(f"  {attr:28s} <- {mod}.{tname}")
