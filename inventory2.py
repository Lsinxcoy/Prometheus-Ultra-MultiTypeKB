"""盘点2: 按管道/功能域归类 Omega 的 70+ 子系统, 并查每类的激活/使用证据."""
import sys, os, inspect
sys.path.insert(0, "E:/Prometheus-Ultra-MultiTypeKB/src")
os.chdir("E:/Prometheus-Ultra-MultiTypeKB")
from prometheus_ultra.life import Omega
om = Omega(db_path="E:/Prometheus-Ultra-MultiTypeKB/src/prometheus_ultra.db")

# 按功能域分组(论文/管道视角)
groups = {
    "记忆层(Memory)": ["store","graph_memory","bridge","consolidation_engine","rumination_engine",
                       "retrospective_memory","memory_depth","memory_context_clash","forbidden_pattern_detector",
                       "subtle_memory_benchmark","x_adapter","y_adapter","memory_data_adapter","memory_write_guard"],
    "安全层(Safety)": ["five_gates","five_gate_chain","input_guardrail","output_guardrail","instincts",
                       "data_exfil_detector","drift_detector","finetune_audit","intervention_controller",
                       "leakage_detector","loop_guard","memory_side_effect","process_auditor","trace_engine",
                       "trigger_detector","tool_tax_gate","owner_harm"],
    "进化(Evolution)": ["evolution_engine","anti_evolution","evo_quality_gates","eval_engine","semantic_evolution",
                        "memento_evolution","persona_manager","evolution_grill","evolution_state"],
    "推理/Harness": ["harness_x","adaptive_harness","brain","context_engineering","reasoning_adapter",
                     "crash_restore","dag_executor"],
    "生命周期(Lifecycle)": ["cerebral_cortex","autonomic_regulator","sleep_gate","event_bus"],
    "Loop/规划": ["brainstorming","loop_selector","verification_gate","agent_forest","tool_loop",
                  "organ_pipeline","confidence_gate"],
    "协作(Collaboration)": ["multi_agent","agent_reputation","skill_claw","skill_registry"],
    "机制注册": ["mechanism_registry"],
}
for gname, keys in groups.items():
    print(f"\n### {gname} ({len(keys)} 个)")
    for k in keys:
        v = getattr(om, k, None)
        if v is None:
            print(f"  [缺失] {k}")
            continue
        # 找激活/计数证据
        ev = []
        for fld in ("enabled","active","activated","_enabled","is_active","status","_checks","invoke_count","used_count"):
            if hasattr(v, fld):
                ev.append(f"{fld}={getattr(v,fld)}")
        # 找方法数(机制复杂度)
        methods = [m for m,_ in inspect.getmembers(v, inspect.ismethod) if not m.startswith('_')]
        print(f"  {k:24s} :: {type(v).__name__} | 证据:{ev[:4]} | 方法数={len(methods)}")
