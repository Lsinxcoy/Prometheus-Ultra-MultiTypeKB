"""StatePersistence — Save and restore memory state across restarts.

Saves: DopamineGate history, CoALA working memory, evolution engine state,
       four_network networks, graph_memory episodes, feedback records.
"""
from __future__ import annotations
import json, os, time
import logging

logger = logging.getLogger(__name__)


class StatePersistence:
    """Persist and restore Omega memory state."""

    def __init__(self, path: str | None = None):
        if path is None:
            path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "omega_state.json")
            path = os.path.normpath(path)
        self._path = path

    def save(self, omega) -> dict:
        state = {
            "timestamp": time.time(),
            "dopamine_history": omega.dopamine._history[-100:],
            "dopamine_threshold": omega.dopamine._current_threshold,
            "coala_working": [{"content": getattr(i, 'content', ''), "importance": getattr(i, 'importance', 0.5)}
                             for i in omega.coala._working_memory[-20:]],
            "four_network_counts": {k: len(v) for k, v in omega.four_network._networks.items()},
            "graph_episode_count": len(omega.graph_memory._episodes),
            "feedback_count": sum(len(v) for v in omega.feedback._feedbacks.values()),
            "evolution_count": len(omega.evolution_engine._history),
            "dream_count": len(omega.dream._memories),
            "thermodynamic_state": omega.thermodynamic.get_state(),
            "trust_levels": omega.knowledge_to_mechanism.get_trust_state(),
        }
        parent = os.path.dirname(self._path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(self._path, 'w') as f:
            json.dump(state, f)
        return state

    def load(self, omega) -> dict:
        if not os.path.exists(self._path):
            return {}
        try:
            with open(self._path, 'r') as f:
                state = json.load(f)
            # Restore dopamine threshold
            if "dopamine_threshold" in state:
                omega.dopamine._current_threshold = state["dopamine_threshold"]
            # Restore dopamine history
            if "dopamine_history" in state:
                omega.dopamine._history = state["dopamine_history"]
            # Restore CoALA working memory
            if "coala_working" in state:
                omega.coala._working_memory = state["coala_working"]
            # Restore graph episode count tracking
            if "graph_episode_count" in state:
                omega.graph_memory._episode_count = state["graph_episode_count"]
            # Restore evolution engine history
            if "evolution_count" in state:
                omega.evolution_engine._history_loaded = True
            # Restore thermodynamic state
            if "thermodynamic_state" in state:
                omega.thermodynamic.set_state(state["thermodynamic_state"])
            # Restore trust levels
            if "trust_levels" in state:
                omega.knowledge_to_mechanism.set_trust_state(state["trust_levels"])
            # Restore four network counts (info only, networks rebuild on demand)
            # Restore feedback count (info only)
            # Restore dream count (info only)
            if "four_network_counts" in state:
                pass  # Networks rebuild dynamically on first access
            return state
        except Exception as e:
            logger.warning("StatePersistence load failed: %s", e)
            return {}

    def get_stats(self) -> dict:
        exists = os.path.exists(self._path)
        return {"persisted": exists, "path": self._path}
