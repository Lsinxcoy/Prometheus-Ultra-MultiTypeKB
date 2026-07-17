import pytest
from prometheus_ultra.learning.knowledge_rumination import KnowledgeRuminationEngine

def test_rumination_publishes_event():
    published = []
    class StubBus:
        def publish(self, ev): published.append(ev)
        def subscribe(self, *a, **k): pass
    class StubOmega:
        event_bus = StubBus()
        def _compute_fitness(self): return 0.5
    eng = KnowledgeRuminationEngine.__new__(KnowledgeRuminationEngine)
    eng.omega = StubOmega()
    eng.history = []
    eng.last_full_rumination = 0
    eng.last_incremental_rumination = 0
    eng.full_interval_seconds = 999999
    eng.incremental_interval_seconds = 999999
    eng._select_nodes = lambda mode, limit: []
    res = eng.ruminate(mode="full", force=True)
    assert any(e.get("type") == "rumination_completed" for e in published), "rumination 必须 publish rumination_completed"
    ev = [e for e in published if e.get("type")=="rumination_completed"][0]
    assert "data" in ev and "total_scanned" in ev["data"]

def test_cns_subscribes_rumination():
    from prometheus_ultra.lifecycle.cns_orchestrator import CNSOrchestrator
    subs = []
    class StubBus:
        def subscribe(self, topic, handler, priority=0.5):
            subs.append(topic)
    cns = CNSOrchestrator.__new__(CNSOrchestrator)
    cns.subscribe(StubBus())
    assert "rumination_completed" in subs, "CNS 必须订阅 rumination_completed"
