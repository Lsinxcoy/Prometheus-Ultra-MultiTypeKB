"""运行期验证: 不依赖历史文档, 直接实例化并调用机制, 看是否真有算法行为.

判定标准(运行期, 非记忆):
- 同一输入多次调用, 输出是否变化(真算法有随机性/状态演化) -> 非 MOCK
- 不同输入是否产生不同输出 -> 非硬编码
- 是否真修改内部状态(种群/策略/success_rate) -> 真在跑
"""
import sys, os, inspect
sys.path.insert(0, "E:/Prometheus-Ultra-MultiTypeKB/src")
os.chdir("E:/Prometheus-Ultra-MultiTypeKB")
from prometheus_ultra.life import Omega

om = Omega(db_path="E:/Prometheus-Ultra-MultiTypeKB/src/prometheus_ultra.db")

def try_call(obj, method, *args, **kwargs):
    """尝试调用机制方法, 捕获异常, 返回(成功, 输出repr前120字, 是否改变状态)."""
    if not hasattr(obj, method):
        return f"[无{method}]"
    fn = getattr(obj, method)
    try:
        before = repr(getattr(obj, "_strategies", getattr(obj, "_population", getattr(obj, "_history", None))))[:60]
        r = fn(*args, **kwargs)
        after = repr(getattr(obj, "_strategies", getattr(obj, "_population", getattr(obj, "_history", None))))[:60]
        out = repr(r)[:120]
        changed = before != after
        return f"OK | 状态变={changed} | out={out}"
    except Exception as e:
        return f"[异常:{type(e).__name__}:{str(e)[:60]}]"

print("=== reasoning_bank ===")
print("  evolve:", try_call(om.reasoning_bank, "evolve", "solve math", {"type": "optimization"}))
print("  evolve2:", try_call(om.reasoning_bank, "evolve", "write essay", {"type": "research"}))

print("=== openspace ===")
try:
    r1 = om.openspace.evolve("optimize", generations=3)
    r2 = om.openspace.evolve("explore", generations=3)
    print(f"  evolve1 best_fitness={getattr(r1,'best_fitness',None):.4f} niches={getattr(r1,'num_niches',None)}")
    print(f"  evolve2 best_fitness={getattr(r2,'best_fitness',None):.4f} niches={getattr(r2,'num_niches',None)}")
    print(f"  不同输入产出不同: {r1.best_fitness != r2.best_fitness or r1.num_niches != r2.num_niches}")
except Exception as e:
    print(f"  [异常:{e}]")

print("=== eval_engine (M* GA) ===")
try:
    r = om.eval_engine.evolve("test")
    print(f"  evolve fitness_history_len={len(getattr(r,'fitness_history',[]))} gen={getattr(r,'generation',None)}")
except Exception as e:
    print(f"  [异常:{e}]")

print("=== coevolve (Red Queen) ===")
try:
    r = om.coevolve.evolve(["ctx1"])
    print(f"  evolve ok, type={type(r).__name__}")
except Exception as e:
    print(f"  [异常:{type(e).__name__}:{e}]")

print("=== deep_retrofit_6 ===")
try:
    r = om.deep_retrofit_6.execute("test topic", source_content="This is a test. It has two sentences. Another point here.")
    print(f"  execute all_completed={r.all_completed} steps={len(r.steps)} insights={len(r.key_insights)} mods={len(r.behavior_modifications)}")
except Exception as e:
    print(f"  [异常:{type(e).__name__}:{e}]")

print("=== lotka_volterra ===")
try:
    om.lotka_volterra.add_species("A", 1.0)
    om.lotka_volterra.add_species("B", 0.5)
    r = om.lotka_volterra.simulate(dt=0.1)
    print(f"  simulate ok, history_len={len(getattr(r,'history',[]))}")
except Exception as e:
    print(f"  [异常:{type(e).__name__}:{e}]")
