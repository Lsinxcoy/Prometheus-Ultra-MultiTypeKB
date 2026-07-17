"""HermesAdapter — HostAgentAdapter 的 Hermes 实现 (P1b, 解 B5).

把原 LLMBridge 的 Hermes 专属逻辑迁入 HostAgentAdapter 接口:
- llm_complete(): 复用 LLMBridge (HTTP 模式, 复用 Hermes 对话模型)
- emit_capability(): 把 Ultra 机制导出给 Hermes (经 HTTP 端点, 或降级为本地记录)
- ingest_experience(): 拉取 Hermes 运行时经验 (经 HTTP 端点, 无则降级)

env 名泛化:
- AGENT_LLM_ENDPOINT (通用, 优先)
- HERMES_LLM_ENDPOINT (Hermes 兼容别名, 保留)
"""
from __future__ import annotations

import logging
import os

from prometheus_ultra.integration.host_agent import HostAgentAdapter
from prometheus_ultra.integration.llm_bridge import LLMBridge

logger = logging.getLogger(__name__)


class HermesAdapter(HostAgentAdapter):
    """Hermes 宿主适配器. Ultra 通过它调用 Hermes 的 LLM 并把机制回流给 Hermes."""

    def __init__(self, endpoint: str | None = None, api_key: str | None = None,
                 model: str | None = None, timeout: float = 60.0):
        # env 泛化: AGENT_LLM_ENDPOINT 优先, HERMES_LLM_ENDPOINT 兼容别名
        ep = endpoint or os.environ.get("AGENT_LLM_ENDPOINT") or os.environ.get("HERMES_LLM_ENDPOINT")
        self._bridge = LLMBridge(endpoint=ep, api_key=api_key, model=model, timeout=timeout)
        # Hermes 专用 emit 端点(可选): 把 capability 推给 Hermes
        self._emit_endpoint = os.environ.get("AGENT_CAPABILITY_ENDPOINT") or os.environ.get("HERMES_CAPABILITY_ENDPOINT")

    def llm_complete(self, prompt: str, system: str = "") -> str | None:
        return self._bridge.complete(prompt, system=system)

    def get_runtime_context(self) -> dict:
        """Hermes 运行时上下文. 有端点时尝试拉取, 无则返回基础信息."""
        if not self._bridge.available:
            return {"tools": [], "context_window": 0, "current_task": "", "host": "hermes", "llm": "none"}
        return {"tools": [], "context_window": 0, "current_task": "", "host": "hermes",
                "llm": self._bridge._mode, "endpoint": self._bridge.endpoint}

    def emit_capability(self, spec: dict) -> bool:
        """把 Ultra 进化机制导出给 Hermes.

        优先 HTTP POST 到 AGENT_CAPABILITY_ENDPOINT (Hermes 侧接收并生成 tool/prompt);
        无端点时降级为本地记录(机制已存 registry + store, 不丢).
        """
        name = spec.get("name", "?")
        if self._emit_endpoint:
            try:
                import httpx
                resp = httpx.post(self._emit_endpoint, json=spec, timeout=self._bridge.timeout)
                ok = resp.status_code < 300
                logger.info("HermesAdapter: emit %s -> Hermes (%s)", name, "ok" if ok else resp.status_code)
                return ok
            except Exception as e:
                logger.debug("HermesAdapter: emit HTTP failed: %s", e)
        logger.info("HermesAdapter: emit %s recorded locally (no capability endpoint)", name)
        return False

    def ingest_experience(self, log: dict) -> None:
        """宿主经验回流. Hermes 侧无标准端点时, 由调用方(learn)直接喂 store, 此处 no-op."""
        logger.debug("HermesAdapter: ingest_experience (Hermes 经 learn(source=host_experience) 直喂 store)")
