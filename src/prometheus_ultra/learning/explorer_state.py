"""ExplorerState — Track exploration rounds and focus areas.

基于:
- MiMo Self-Evolution 探索状态追踪 (X系统) + 信息增益驱动的自适应探索
  - 轮次计数: 每日探索轮次追踪, ≥10轮触发修订, ≥20轮停止
  - 焦点领域索引: 按domain统计探索频率, max(domain_counts) = 焦点
  - 信息增益记录: 每轮记录info_gain, 持久化到explorer_state.json
  - 自适应决策: should_insert_revision/should_stop 基于轮次阈值

来源: Omega系统 explorer_state 探索状态追踪模块 + MiMo自我进化框架
"""
from __future__ import annotations



import logging
import time, json, os
from dataclasses import dataclass, field
logger = logging.getLogger(__name__)


@dataclass
class ExplorationRound:
    round_num: int = 0
    topic: str = ""
    domain: str = ""
    info_gain: float = 0.0
    timestamp: float = 0.0


class ExplorerState:
    """Track exploration progress and focus areas."""
    def __init__(self, path: str | None = None):
        if path is None:
            path = os.path.join(os.path.dirname(__file__), "..", "..", "..", "explorer_state.json")
            path = os.path.normpath(path)
        self._path = path
        self._today_rounds: list[dict] = []
        self._domain_counts: dict[str, int] = {}
        self._total_rounds: int = 0
        self._load()

    def _load(self):
        if os.path.exists(self._path):
            try:
                with open(self._path, 'r') as f:
                    data = json.load(f)
                self._today_rounds = data.get("today", [])
                self._domain_counts = data.get("domains", {})
                self._total_rounds = data.get("total", 0)
            except Exception as e:
                logger.warning("Failed to load explorer state: %s", e)

    def _flush(self):
        parent = os.path.dirname(self._path)
        if parent:
            os.makedirs(parent, exist_ok=True)
        with open(self._path, 'w') as f:
            json.dump({"today": self._today_rounds[-50:],
                       "domains": self._domain_counts,
                       "total": self._total_rounds}, f)

    def record_round(self, topic: str, domain: str, info_gain: float):
        r = {"topic": topic, "domain": domain, "gain": info_gain, "ts": time.time()}
        self._today_rounds.append(r)
        self._domain_counts[domain] = self._domain_counts.get(domain, 0) + 1
        self._total_rounds += 1
        self._flush()

    def today_count(self) -> int:
        today = time.strftime('%Y-%m-%d')
        return sum(1 for r in self._today_rounds if time.strftime('%Y-%m-%d', time.localtime(r['ts'])) == today)

    def should_insert_revision(self) -> bool:
        return self.today_count() >= 10

    def should_stop(self) -> bool:
        return self.today_count() >= 20

    def get_focus_domain(self) -> str:
        if not self._domain_counts:
            return ""
        return max(self._domain_counts, key=self._domain_counts.get)

    def reset_today(self):
        self._today_rounds = []
        self._flush()

    def get_stats(self) -> dict:
        return {"today": self.today_count(), "total": self._total_rounds,
                "domains": len(self._domain_counts)}
