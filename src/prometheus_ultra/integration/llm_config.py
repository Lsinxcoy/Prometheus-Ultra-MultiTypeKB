"""LLMConfig — Agent LLM 配置注入/自动复用协议 [V3.0 G2 / V3.7 自动化].

设计目的(用户设想):
- Ultra 作为独立进程运行, 自身进化不依赖 Agent.
- 但 T3(机制提取) + T4(论文编译) 必须复用 Agent 的 LLM 模型配置,
  才能真正编译出机制(否则生成占位 draft_code, 无真能力).

关键修正(V3.7, 用户要求"让 Ultra 自动复用 Agent 的 LLM 配置,
和代理没有任何关系"):
- 之前退化为"env 注入优先 + 人工步骤" — 与 V3.0 G2 的"自动复用"自相矛盾.
- 现改为: Omega 启动时**自动探测并复用宿主 Agent(Hermes)的 LLM 配置**,
  优先级: env 注入 > Hermes config.yaml 的 model 段 > 探测 Hermes 暴露的本地 LLM 代理端口.
- 代理(clash 等)只是网络通道, 与 LLM 配置复用完全解耦.

协议(env 注入, 仅内存):
- AGENT_LLM_ENDPOINT / HERMES_LLM_ENDPOINT : OpenAI 兼容 chat completions URL
- AGENT_LLM_API_KEY  : [REDACTED] 仅内存, 不落盘
- AGENT_LLM_MODEL    : 模型名(可选)
- AGENT_LLM_PROVIDER : openai / hermes / self-hosted (可选, 自动探测)
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
            api_key=os.environ.get("AGENT_LLM_API_KEY", ""),  # [REDACTED]
            model=os.environ.get("AGENT_LLM_MODEL", ""),
            provider=os.environ.get("AGENT_LLM_PROVIDER", "auto"),
        )

    @classmethod
    def from_hermes(cls) -> "LLMConfig | None":
        """自动探测 Hermes 宿主的 LLM 配置(与代理无关, 纯配置层自动复用).

        探测顺序(严格不依赖网络代理):
        1. env 注入 (AGENT_LLM_* / HERMES_LLM_*)  — 最高优先, 人工覆盖
        2. Hermes config.yaml 的 model 段 (base_url + api_key + model) — 持久化配置
        3. 探测 Hermes 可能暴露的本地 LLM 代理端口 (127.0.0.1:PORT/v1/chat/completions)
           — 未来 Hermes 若起本地 LLM 代理, Ultra 自动复用
        全部失败返回 None (T4 诚实降级, 非崩溃).
        """
        # 1. env 优先
        env_cfg = cls.from_env()
        if env_cfg is not None:
            return env_cfg
        # 2. Hermes config.yaml 的 model 段
        try:
            import yaml
            cfg_path = os.path.join(os.path.expanduser("~"), ".hermes", "config.yaml")
            if os.path.exists(cfg_path):
                with open(cfg_path, "r", encoding="utf-8") as f:
                    cfg = yaml.safe_load(f) or {}
                m = cfg.get("model", {}) or {}
                ep = m.get("base_url") or m.get("endpoint")
                if ep:
                    return cls(
                        endpoint=ep,
                        api_key=m.get("api_key", ""),  # [REDACTED]
                        model=m.get("default") or m.get("model") or "",
                        provider=m.get("provider", "auto"),
                    )
        except Exception as e:
            logger.debug("LLMConfig.from_hermes: config.yaml 探测失败 %s", e)
        # 3. 探测本地 LLM 代理端口(未来扩展点, 当前不强制)
        #    (保留接口: 若 Hermes 起 127.0.0.1:PORT 的 OpenAI 兼容代理, 此处自动发现)
        # 4. 全部失败
        return None

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
