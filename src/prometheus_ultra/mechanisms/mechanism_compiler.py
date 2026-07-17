"""MechanismCompiler — T4 第四轨: 将论文编译为新机制草案。

与前三轨本质区别: 创造系统原本不存在的机制(超前探索), 而非调参/重组/搬已知。

流程:
1. SourceFetcher 拉论文全文(arxiv e-print)
2. LLM(复用 Hermes 对话模型)把核心机制编译为 draft module:
   - 机制描述 + 接口契约(input/output/依赖) + Python 骨架(继承 BaseMechanism)
   无 LLM 时降级为规则提取(识别 'we propose'/'algorithm'/'method' 段)
3. draft 存 archive/compiled/{name}.py + 注册进 registry(status='compiled', 不直启)
4. 激活由验证门 + S7 神经系统决定(A-B 并行, 不自动直替)

安全: 编译产物默认不执行, 仅存草稿待验证。
"""
from __future__ import annotations

import logging
import os
import re

from prometheus_ultra.mechanisms.base_mechanism import BaseMechanism
from prometheus_ultra.mechanisms.source_fetcher import fetch_arxiv_fulltext

logger = logging.getLogger(__name__)


class CompiledMechanism(BaseMechanism):
    """T4 编译出的机制草案(来自论文), 作为候选进入 registry。"""

    def __init__(self, name: str, description: str, paper: str, draft_code: str = ""):
        super().__init__()
        self.name = name
        self.description = description
        self.paper = paper
        self.draft_code = draft_code
        self.category = "compiled"

    def run(self, context: dict | None = None) -> dict:
        """编译草案默认不执行(待验证), 仅返回草案信息。"""
        return {
            "ok": True,
            "mechanism": self.name,
            "source_paper": self.paper,
            "draft_code_len": len(self.draft_code),
            "note": "compiled draft (candidate, not auto-activated)",
        }


class MechanismCompiler:
    """将论文编译为机制草案。"""

    def __init__(self, llm=None, store=None, compiled_dir: str = "archive/compiled"):
        self.llm = llm
        self._store = store
        self.compiled_dir = compiled_dir
        os.makedirs(self.compiled_dir, exist_ok=True)

    def compile(self, arxiv_id: str, paper_title: str = "") -> CompiledMechanism | None:
        fulltext = fetch_arxiv_fulltext(arxiv_id)
        if not fulltext:
            logger.debug("MechanismCompiler: no fulltext for %s", arxiv_id)
            return None

        mechanism_name = f"paper_{arxiv_id.split('/')[-1].replace('.', '_')}"
        description = ""
        draft_code = ""

        if self.llm is not None and self.llm.available:
            prompt = (
                f"从以下论文全文提取其'核心机制/算法', 并编译为可注册的 Python 机制草案。\n"
                f"论文: {paper_title}\n\n{fulltext[:8000]}\n\n"
                f"输出:\nMECHANISM: <机制名>\n"
                f"WHAT: <一句话>\n"
                f"CONTRACT: <输入/输出/依赖>\n"
                f"DRAFT:\n```python\n"
                f"from prometheus_ultra.mechanisms.base_mechanism import BaseMechanism\n"
                f"class X(BaseMechanism):\n    name='...'\n    def run(self, context=None):\n        ...\n```"
            )
            out = self.llm.complete(prompt, system="你是机制编译器, 输出机制草案")
            if out:
                description = out
                draft_code = out

        # 降级: 规则提取(识别 we propose / algorithm / method 段)
        if not description:
            proposals = re.findall(r"(?:we propose|our method|algorithm \d+|our approach)[^\n.]{0,120}", fulltext, re.I)
            description = f"从 {arxiv_id} 提取: " + " | ".join(proposals[:3])
            draft_code = f"# draft stub for {arxiv_id}\n# {description[:200]}"

        # 存草稿文件
        try:
            fname = os.path.join(self.compiled_dir, f"{mechanism_name}.py")
            with open(fname, "w", encoding="utf-8") as f:
                f.write(f'"""Compiled from {arxiv_id}: {paper_title}\\n\\n{description}\\n"""\n\n')
                f.write("from prometheus_ultra.mechanisms.base_mechanism import BaseMechanism\n\n")
                f.write(f"class {mechanism_name}(BaseMechanism):\n")
                f.write(f"    name = '{mechanism_name}'\n")
                f.write(f"    description = '''{description[:300]}'''\n")
                f.write(f"    category = 'compiled'\n\n")
                f.write("    def run(self, context=None):\n")
                f.write("        return {'ok': True, 'note': 'compiled draft, awaiting verification'}\n")
        except Exception as e:
            logger.debug("MechanismCompiler: save draft failed: %s", e)

        return CompiledMechanism(
            name=mechanism_name, description=description, paper=arxiv_id, draft_code=draft_code
        )

    def compile_from_node(self, node) -> CompiledMechanism | None:
        """P3: 从 learn 已吸收的 rail_t4 节点取 url, 编译机制(不重拉源)。

        消费 store 中 NodeType.PAPER / rail_t4 节点(learn 已吸收论文),
        直接取 node.url 中的 arxiv_id 拉全文, 而非自己重新扫描 arxiv。消除源重复。
        """
        if node is None:
            return None
        url = getattr(node, "url", "") or ""
        if not url:
            logger.debug("MechanismCompiler: node %s has no url", getattr(node, "id", "?"))
            return None
        # url 形如 https://arxiv.org/abs/2401.12345 -> 2401.12345
        arxiv_id = url.replace("https://arxiv.org/abs/", "").strip("/")
        if not arxiv_id or "." not in arxiv_id:
            logger.debug("MechanismCompiler: invalid arxiv url %s", url)
            return None
        title = getattr(node, "content", "")[:80]
        return self.compile(arxiv_id, title)

    def register_from_node(self, node, registry, paper_title: str = "") -> dict:
        """从节点编译并注册进机制表(status=compiled, 不激活)。

        P4: 同时写 store 的 PATTERN 节点(统一存储), 并建立
        PROVENANCE_DERIVED_FROM 边连回源论文节点。
        """
        mech = self.compile_from_node(node)
        if mech is None:
            return {"registered": False, "reason": "fetch_failed"}
        result = registry.register(
            mech.name,
            data={"executable": mech, "paper": mech.paper, "draft_code": mech.draft_code},
            dependencies=[],
            category="compiled",
            pending=True,  # P6: T4 产物默认 pending, 待验证激活(不自动直替生产)
        )
        # P4: 写 store 节点(统一知识底座)
        try:
            store = getattr(registry, "store", None) or getattr(self, "_store", None)
            if store is not None:
                from prometheus_ultra.foundation.schema import Node, NodeType, Edge, EdgeType
                store.create_node(Node(
                    content=f"[T4 compiled] {(mech.description or '')[:300]}",
                    type=NodeType.PATTERN, tags=["mechanism", "compiled", mech.name],
                    utility=0.6, url=getattr(node, "url", ""),
                ))
                nid = getattr(node, "id", None)
                if nid:
                    try:
                        store.create_edge(Edge(source_id=nid, target_id=mech.name,
                                               type=EdgeType.PROVENANCE_DERIVED_FROM, weight=1.0))
                    except Exception:
                        pass
        except Exception as e:
            logger.debug("MechanismCompiler: store write failed: %s", e)

        # P6: 激活闭环 — 注册为 pending 后立刻走三道门验证, 通过则 activate
        try:
            act = registry.verify_and_activate(
                mech.name,
                claim=(mech.description or mech.name),
                hypothesis=f"T4:{mech.name} from {mech.paper}",
            )
            result["activated"] = act.get("activated", False)
            result["activation"] = act
            store = getattr(registry, "store", None) or getattr(self, "_store", None)
            if store is not None and act.get("activated"):
                try:
                    pats = store.get_nodes_by_type(NodeType.PATTERN, limit=1000)
                    for p in pats:
                        if mech.name in (p.tags or []):
                            p.tags = list(p.tags or []) + ["active"]
                            store.update_node(p)
                            break
                except Exception:
                    pass
        except Exception as e:
            logger.debug("MechanismCompiler: activation failed: %s", e)
        return result

    def register(self, arxiv_id: str, registry, paper_title: str = "") -> dict:
        """向后兼容: 旧接口(直接传 arxiv_id 编译+注册)。新代码请用 register_from_node。"""
        mech = self.compile(arxiv_id, paper_title)
        if mech is None:
            return {"registered": False, "reason": "fetch_failed"}
        return registry.register(
            mech.name,
            data={"executable": mech, "paper": mech.paper, "draft_code": mech.draft_code},
            dependencies=[],
            category="compiled",
        )
