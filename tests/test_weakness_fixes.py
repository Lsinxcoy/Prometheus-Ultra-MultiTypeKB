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
from prometheus_ultra.loop.info_gain import InfoGainCalculator


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


def test_read_entries_surfaces_malformed_inbox_line(caplog, tmp_path):
    """cycle3: inbox 中腐蚀 JSON 行不再静默丢失, 而是告警(此前 except:pass 无声吞掉)。"""
    import json
    import logging

    from prometheus_ultra.integration.capability_inbox import CapabilityInbox

    inbox_path = tmp_path / "inbox.jsonl"
    with open(inbox_path, "w", encoding="utf-8") as f:
        f.write(json.dumps({"event": "received", "name": "good_mech"}) + "\n")
        f.write("{ 这一行是损坏的 JSON \n")  # 非法 JSON

    caplog.set_level(logging.WARNING,
                     logger="prometheus_ultra.integration.capability_inbox")
    inbox = CapabilityInbox(path=str(inbox_path))

    entries = inbox._read_entries()
    # 合法行仍正常解析
    assert len(entries) == 1
    assert entries[0]["name"] == "good_mech"
    # 损坏行触发告警 —— 证明不再静默吞掉(修复前此处零日志)
    assert any("损坏的 inbox 行" in r.message for r in caplog.records), \
        "腐蚀 inbox 行应触发告警, 但无任何日志(静默丢失未修复)"


def test_load_applied_surfaces_malformed_record(caplog, tmp_path):
    """cycle3: 腐蚀的 applied 记录不再静默跳过, 而是告警(防 pending() 重复报已应用机制)。"""
    import json
    import logging
    import os

    from prometheus_ultra.integration.capability_inbox import CapabilityInbox

    inbox_path = tmp_path / "inbox.jsonl"
    inbox_path.write_text("", encoding="utf-8")
    inbox = CapabilityInbox(path=str(inbox_path))  # 启动时 applied/ 不存在, 安全

    applied_dir = os.path.join(os.path.dirname(str(inbox_path)), "applied")
    os.makedirs(applied_dir, exist_ok=True)
    # 腐蚀的 applied 记录
    with open(os.path.join(applied_dir, "bad.applied.json"), "w", encoding="utf-8") as f:
        f.write("{ corrupted json")
    # 合法 applied 记录
    good = {"name": "good_mech", "host_id": "default", "applied_at": 1.0}
    with open(os.path.join(applied_dir, "good_mech.applied.json"), "w", encoding="utf-8") as f:
        json.dump(good, f)

    caplog.set_level(logging.WARNING,
                     logger="prometheus_ultra.integration.capability_inbox")
    inbox._load_applied()

    # 合法记录仍加载
    assert "good_mech" in inbox._applied
    # 腐蚀记录触发告警且不崩(修复前 except:pass 无声吞掉 -> 重启后 pending 重报机制)
    assert any("损坏的 applied 记录" in r.message for r in caplog.records), \
        "腐蚀 applied 记录应触发告警, 但无任何日志(静默丢失未修复)"


# ===== cycle4: InfoGainCalculator.record_gain / diminishing_returns 未实现方法修复 =====
def test_record_gain_stores_history():
    """record_gain 真实落地: 累积历史(此前是 return float(value) 的 no-op, 历史永不增长)。"""
    ig = InfoGainCalculator()
    assert ig._gains == []
    ret = ig.record_gain("reflect", 0.42)
    assert ret == 0.42            # 兼容别名: 原样返回
    ig.record_gain("reflect", 0.3)
    assert len(ig._gains) == 2
    assert ig._gains == [0.42, 0.3]


def test_diminishing_returns_false_without_history():
    """样本不足时仍返回 False(保留安全默认, 不崩、不误报)。"""
    ig = InfoGainCalculator()
    assert ig.diminishing_returns() is False


def test_diminishing_returns_detects_clear_diminishing():
    """增益明显边际递减时返回 True(此前恒返回 False, 永远检测不到)。"""
    ig = InfoGainCalculator()
    for v in [1.0, 0.9, 0.8, 0.1, 0.05, 0.02]:
        ig.record_gain("reflect", v)
    assert ig.diminishing_returns() is True


def test_diminishing_returns_false_when_increasing():
    """增益持续上升时不误报递减(近期均值 > 前期均值)。"""
    ig = InfoGainCalculator()
    for v in [0.1, 0.2, 0.3, 0.4, 0.5, 0.6]:
        ig.record_gain("reflect", v)
    assert ig.diminishing_returns() is False


def test_diminishing_returns_no_args_callable_like_life():
    """life.py 以无参方式调用 diminishing_returns(), 签名须保持兼容且平稳时返回 False。"""
    ig = InfoGainCalculator()
    for v in [0.5, 0.5, 0.5, 0.5, 0.5, 0.5]:
        ig.record_gain("reflect", v)
    assert ig.diminishing_returns() is False
