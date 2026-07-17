"""UtilityDecay — Knowledge utility tracking with decay rules.

Based on: MiMo Daily Learning #5.2 (效用追踪)

Rules from MiMo:
    - Initial score: 0-5 (assessed at exploration time)
    - Referenced in exploration: +2
    - 30 days unused: -1
    - utility < 3 AND > 30 days → candidate for deletion
    - MEMORY.md only keeps utility >= 3
    - Knowledge总量 > 500KB → trigger compression

Memory vs Knowledge layer:
    - Memory layer (behavior rules): decay applies, 30 days unused → candidate delete
    - Knowledge layer (facts/frameworks): no decay, only supersedes replacement
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)


import time
from dataclasses import dataclass


@dataclass
class UtilityEntry:
    item_id: str = ""
    score: float = 3.0
    created_at: float = 0.0
    last_referenced: float = 0.0
    reference_count: int = 0
    layer: str = "knowledge"  # memory or knowledge
    is_candidate_for_deletion: bool = False


class UtilityDecay:
    """Knowledge utility tracking with decay rules.

    Based on MiMo Daily Learning System.

    Usage:
        ud = UtilityDecay()

        # Register knowledge
        ud.register("k001", initial_score=4.0, layer="knowledge")

        # Reference increases score
        ud.reference("k001")  # +2

        # Apply daily decay
        ud.apply_decay(days_elapsed=30)

        # Check what should be cleaned
        candidates = ud.get_deletion_candidates()
    """

    REFERENCE_BOOST = 2.0
    DECAY_PER_30_DAYS = 1.0
    DELETION_THRESHOLD = 3.0
    DELETION_DAYS_UNUSED = 30
    MEMORY_MAX_ENTRIES = 200
    KNOWLEDGE_MAX_SIZE_KB = 500

    def __init__(self):
        self._entries: dict[str, UtilityEntry] = {}
        self._stats = {"registered": 0, "referenced": 0, "decayed": 0, "deleted": 0}

    def register(self, item_id: str, initial_score: float = 3.0,
                 layer: str = "knowledge") -> UtilityEntry:
        """Register a knowledge item."""
        entry = UtilityEntry(
            item_id=item_id,
            score=max(0, min(5, initial_score)),
            created_at=time.time(),
            last_referenced=time.time(),
            layer=layer,
        )
        self._entries[item_id] = entry
        self._stats["registered"] += 1
        return entry

    def reference(self, item_id: str) -> bool:
        """Reference a knowledge item (+2 score)."""
        if item_id not in self._entries:
            return False

        entry = self._entries[item_id]
        entry.score = min(5.0, entry.score + self.REFERENCE_BOOST)
        entry.last_referenced = time.time()
        entry.reference_count += 1
        entry.is_candidate_for_deletion = False
        self._stats["referenced"] += 1
        return True

    def apply_decay(self, days_elapsed: float = 1.0):
        """Apply time-based decay to all entries.

        From MiMo: "30天未引用 → -1"
        """
        now = time.time()
        for entry in self._entries.values():
            days_since_ref = (now - entry.last_referenced) / 86400

            if days_since_ref >= 30 and entry.layer == "memory":
                decay_amount = self.DECAY_PER_30_DAYS * (days_since_ref / 30)
                entry.score = max(0, entry.score - decay_amount)
                self._stats["decayed"] += 1

                if entry.score < self.DELETION_THRESHOLD and days_since_ref > self.DELETION_DAYS_UNUSED:
                    entry.is_candidate_for_deletion = True

    def get_deletion_candidates(self) -> list[UtilityEntry]:
        """Get items candidate for deletion.

        From MiMo: "utility < 3 AND > 30天 → 候选删除"
        """
        return [e for e in self._entries.values() if e.is_candidate_for_deletion]

    def get_memory_items(self) -> list[UtilityEntry]:
        """Get items for MEMORY.md (utility >= 3)."""
        return [e for e in self._entries.values()
                if e.layer == "memory" and e.score >= self.DELETION_THRESHOLD]

    def get_all_entries(self) -> list[UtilityEntry]:
        return list(self._entries.values())

    def get_stats(self) -> dict:
        return dict(self._stats)
