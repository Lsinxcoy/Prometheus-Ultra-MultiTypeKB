"""EvolutionState — T1 进化状态跨会话持久化。

解决: EvolutionEngine 的 gene_specs / 最佳染色体进程内, 重启即丢,
导致进化无累积(每次从零)。本模块把状态序列化到本地 JSON 文件
(进化状态是全局配置, 非知识节点, 用文件比污染 store 更干净)。
"""
from __future__ import annotations

import json
import logging
import os

logger = logging.getLogger(__name__)

STATE_KEY = "evo_state:v1"
DEFAULT_PATH = "archive/evo_state.json"


class EvolutionState:
    """进化状态存取(文件持久化)。"""

    def __init__(self, store=None, path: str = DEFAULT_PATH):
        self.store = store
        self.path = path
        os.makedirs(os.path.dirname(path) or ".", exist_ok=True)

    def save(self, engine) -> bool:
        """保存进化引擎状态(gene_specs + 代数)。"""
        try:
            specs = getattr(engine, "_gene_specs", {}) or {}
            state = {
                "gene_specs": {k: list(v) for k, v in specs.items()},
                "generation": getattr(engine, "_generation", 0),
            }
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(state, f)
            return True
        except Exception as e:
            logger.debug("EvolutionState.save failed: %s", e)
            return False

    def load(self, engine) -> bool:
        """恢复进化引擎状态。"""
        try:
            if not os.path.exists(self.path):
                return False
            with open(self.path, "r", encoding="utf-8") as f:
                state = json.load(f)
            specs = {k: tuple(v) for k, v in state.get("gene_specs", {}).items()}
            if specs:
                engine._gene_specs = specs
            if "generation" in state:
                engine._generation = state["generation"]
            return True
        except Exception as e:
            logger.debug("EvolutionState.load failed: %s", e)
            return False

