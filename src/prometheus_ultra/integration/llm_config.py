"""LLMConfig — Agent LLM 配置注入协议 [V3.0 G2].

设计目的(用户设想):
- Ultra 作为独立进程运行, 自身进化不依赖 Agent.
- 但 T3(机制提取) + T4(论文编译) 必须复用 Agent 的 LLM 模型配置,
  才能真正编译出机制(否则生成占位 draft_code, 无真能力).

协议: Agent 启动 Ultra 时注入以下环境变量(仅内存, 不落盘):
- AGENT_LLM_ENDPOINT : OpenAI 兼容 / Hermes / 自托管 chat completions URL
- AGENT_LLM_API_KEY  : [REDACTED] 仅内存, 不写 store/node
- AGENT_LLM_MODEL    : 模型名(可选, 复用对端默认)
- AGENT_LLM_PROVIDER : openai / hermes / self-hosted (可选, 自动探测)

LLMConfig.from_env() 标准化为 LLMBridge(供 mechanism_compiler/scanner 复用现有接口).
"""
from __future__ import annotations

import os
import logging
from dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class LLMConfig:
    endpoint: str
    api_key: str = ""          # [REDACTED] 仅内存, 不持久化
    model: str = ""
    provider: str = "auto"

    @classmethod
    def from_env(cls) -> "LLMConfig | None":
        """从环境变量读 Agent 注入的 LLM 配置. 无 endpoint 返回 None."""
        ep = os.environ.get("AGENT_LLM_ENDPOINT") or os.environ.get("HERMES_LLM_ENDPOINT")
        if not ep:
            return None
        return cls(
            endpoint=ep,
            # [REDACTED] 仅内存, 不写任何持久化存储
            api_key=os.environ.get("AGENT_LLM_API_KEY", ""),
            model=os.environ.get("AGENT_LLM_MODEL", ""),
            provider=os.environ.get("AGENT_LLM_PROVIDER", "auto"),
        )

    def to_llm_bridge(self):
        """转为 mechanism_compiler/scanner 所需的 LLMBridge(复用现有接口, 零重写)."""
        from prometheus_ultra.integration.llm_bridge import LLMBridge
        return LLMBridge(
            endpoint=self.endpoint,
            api_key=self.api_key,       # [REDACTED] 仅内存传递
            model=self.model or None,
        )

    @property
    def available(self) -> bool:
        return bool(self.endpoint)
