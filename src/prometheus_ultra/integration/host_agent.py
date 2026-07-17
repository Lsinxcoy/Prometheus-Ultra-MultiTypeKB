"""HostAgentAdapter — 宿主 agent 抽象层 (P1a, 解 B5/B6/B7).

设计动机(实测证据):
- 原 LLMBridge 把宿主焊成 Hermes (env 名 HERMES_LLM_ENDPOINT, 注释/Bearer 逻辑 Hermes 专属)
- T4 激活机制零回流宿主 (grep emit_capability|to_host 全空)
- learn() 燃料源仅 ScanSource(web/arxiv/github), 无宿主运行时经验源

本抽象让 Ultra 成为"任意 agent 的外挂记忆 + 自进化生命体":
- llm_complete():      宿主的推理入口 (Hermes 走 HTTP, Claude Code 走 SDK, 自研走自己的)
- get_runtime_context(): 宿主的上下文窗口/工具清单/当前任务
- emit_capability():    把 Ultra 进化出的机制导出成宿主可用的能力(tool/prompt/检索策略)
- ingest_experience():   宿主运行时经验(行为日志/失败/反馈)回流进 Ultra 进化燃料

任意宿主只需实现一个 Adapter, 即可即插即用 — Ultra 内核不感知具体宿主.
"""
from __future__ import annotations

import abc
import logging

logger = logging.getLogger(__name__)


class HostAgentAdapter(abc.ABC):
    """宿主 agent 抽象接口. 所有具体宿主(Hermes/Claude Code/AutoGPT/自研)实现此接口."""

    @abc.abstractmethod
    def llm_complete(self, prompt: str, system: str = "") -> str | None:
        """调用宿主的 LLM 完成一次推理. 无可用时返回 None (调用方降级)."""

    @abc.abstractmethod
    def get_runtime_context(self) -> dict:
        """返回宿主运行时上下文: {tools: [...], context_window: int, current_task: str, ...}."""

    @abc.abstractmethod
    def emit_capability(self, spec: dict) -> bool:
        """把 Ultra 进化出的机制导出给宿主.

        spec 结构: {
            "name": 机制名,
            "target_location": {module, lineno, symbol, ...} (来自 P7 行为定位),
            "draft_code": 机制草案,
            "claim": 机制描述,
            "category": "compiled"(T4) / "extracted"(T3),
        }
        返回 True 表示宿主成功接收(宿主可据此生成 tool/prompt/检索策略).
        注意: 这是"建议+宿主确认"语义, 不自动直替宿主生产 (对齐 P6 原则).
        """

    @abc.abstractmethod
    def ingest_experience(self, log: dict) -> None:
        """宿主运行时经验回流进 Ultra 进化燃料.

        log 结构: {source: "host_experience", events: [{type, content, utility, timestamp}], ...}
        Ultra 的 learn() 会消费它, 经 rumination 路由到 T2/T4 燃料 (复用 rail_t1~t4).
        """


class NullHostAdapter(HostAgentAdapter):
    """空宿主适配器: 无宿主时(如独立运行/测试)的安全降级.

    所有方法 no-op 或返回空 — 保证 Ultra 在无宿主环境下仍能自进化
    (机制注册进 registry 但不回流宿主, 不退化为崩溃).
    """

    def llm_complete(self, prompt: str, system: str = "") -> str | None:
        return None

    def get_runtime_context(self) -> dict:
        return {"tools": [], "context_window": 0, "current_task": "", "host": "none"}

    def emit_capability(self, spec: dict) -> bool:
        logger.debug("NullHostAdapter: emit_capability no-op (no host): %s", spec.get("name"))
        return False

    def ingest_experience(self, log: dict) -> None:
        logger.debug("NullHostAdapter: ingest_experience no-op (no host)")
