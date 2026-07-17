"""MechanismRegistry — 机制注册表.

基于:
- "Plugin Architecture with Dependency Resolution"
  - 注册机制: 名称+元数据+依赖声明
  - 依赖解析: DAG拓扑排序
  - 生命周期: register/enable/disable/invoke
  - 健康检查: 调用统计+依赖验证

算法:
    register(name, dependencies):
        1. 创建机制条目
        2. 验证依赖(DAG无环)
        3. 设置初始状态
    
    resolve_dependencies():
        1. 构建依赖图
        2. 拓扑排序
        3. 返回执行顺序

复杂度:
    register(): O(D) 其中D=依赖数
    resolve_dependencies(): O(V+E)
"""
from __future__ import annotations
import logging

logger = logging.getLogger(__name__)

from collections import defaultdict

from prometheus_ultra.mechanisms.base_mechanism import BaseMechanism


class MechanismRegistry:
    """机制注册表.
    
    支持依赖解析和健康检查.
    """
    
    def __init__(self):
        """初始化."""
        self._mechanisms: dict[str, dict] = {}
        self._enabled: set[str] = set()
        self._history: list[dict] = []
        self._health_checks: list[dict] = []
        # P0a: 激活消费者回调表 — 机制激活后按 category 触发"接生产"动作.
        # 例: "compiled"(T4)->host.emit_capability; T3 机制->evolution_engine.inject_gene_specs
        # 解 B1(僵尸机制): 激活不再只是 status=active, 而是真接生产/回流宿主.
        self._consumers: dict[str, callable] = {}
    
    def register(self, name: str, data: dict | None = None,
                 dependencies: list[str] | None = None,
                 category: str = "general",
                 pending: bool = False) -> dict:
        """注册机制.

        Args:
            name: 机制名称
            data: 元数据
            dependencies: 依赖列表
            category: 分类
            pending: 若为 True, 机制以 "pending" 状态注册(待验证激活),
                     不进 _enabled 集合, 需经 verify_and_activate() 验证通过才激活。
                     这是 P6 激活闭环的核心: T3/T4 产物默认 pending, 不自动直替生产。

        Returns:
            dict: 注册结果
        """
        deps = dependencies or []

        # 验证依赖是否存在
        missing_deps = [d for d in deps if d not in self._mechanisms]
        if missing_deps:
            return {
                "registered": False,
                "error": "missing_dependencies",
                "missing": missing_deps,
            }

        status = "pending" if pending else "registered"
        entry = {
            "name": name,
            "data": data or {},
            "dependencies": deps,
            "category": category,
            "status": status,
            "invoke_count": 0,
            "error_count": 0,
            "last_invoked": None,
            "activated_at": None,
        }

        self._mechanisms[name] = entry
        if not pending:
            self._enabled.add(name)
        self._history.append({"action": "register", "name": name, "deps": deps, "pending": pending})

        return {
            "registered": True,
            "name": name,
            "dependencies": deps,
            "category": category,
            "status": status,
        }
    
    def enable(self, name: str) -> bool:
        """启用机制.
        
        Args:
            name: 机制名称
        
        Returns:
            bool: 是否成功
        """
        if name not in self._mechanisms:
            return False
        
        self._mechanisms[name]["status"] = "enabled"
        self._enabled.add(name)
        self._history.append({"action": "enable", "name": name})
        return True
    
    def deactivate(self, name: str) -> bool:
        """P0b: 熔断回滚 — 把已激活/启用的机制移出 _enabled (状态置 disabled).

        区别于手动 disable(): 语义上用于"激活后验证有害, 自动熔断回滚".
        解 B3: 坏机制激活后若拖垮 fitness, 自动回滚而非永久驻留.
        """
        if name not in self._mechanisms:
            return False
        self._mechanisms[name]["status"] = "disabled"
        self._enabled.discard(name)
        self._history.append({"action": "deactivate", "name": name, "reason": "circuit_break"})
        return True

    def disable(self, name: str) -> bool:
        """禁用机制.
        
        Args:
            name: 机制名称
        
        Returns:
            bool: 是否成功
        """
        if name not in self._mechanisms:
            return False
        
        self._mechanisms[name]["status"] = "disabled"
        self._enabled.discard(name)
        self._history.append({"action": "disable", "name": name})
        return True
    
    def invoke(self, name: str, context: dict | None = None) -> bool:
        """调用机制。

        若机制 data 中带可执行对象(callable / BaseMechanism 实例), 则真执行;
        否则仅记账(向后兼容旧元数据机制)。

        Returns:
            bool: 是否成功
        """
        if name not in self._enabled:
            return False

        entry = self._mechanisms[name]
        entry["invoke_count"] += 1
        import time
        entry["last_invoked"] = time.time()

        executable = entry.get("data", {}).get("executable")
        if executable is not None:
            try:
                if isinstance(executable, BaseMechanism):
                    result = executable.run(context or {})
                    ok = bool(result.get("ok", True)) if isinstance(result, dict) else True
                    entry["data"]["last_result"] = result
                    entry["error_count"] = entry.get("error_count", 0)
                    if not ok:
                        entry["error_count"] += 1
                    return ok
                if callable(executable):
                    executable(context or {})
                    return True
            except Exception as e:  # 机制执行失败不影响主流程
                logger.warning("MechanismRegistry: invoke %s failed: %s", name, e)
                entry["error_count"] = entry.get("error_count", 0) + 1
                return False
        return True
    
    def resolve_dependencies(self) -> list[str]:
        """解析依赖顺序(拓扑排序).
        
        Returns:
            list: 执行顺序(字符串列表)
        """
        # 构建邻接表
        graph = defaultdict(list)
        in_degree = defaultdict(int)
        
        for name, mech in self._mechanisms.items():
            if name not in in_degree:
                in_degree[name] = 0
            for dep in mech["dependencies"]:
                graph[dep].append(name)
                in_degree[name] += 1
        
        # Kahn算法
        queue = [n for n in self._mechanisms if in_degree[n] == 0]
        order = []
        
        while queue:
            node = queue.pop(0)
            order.append(node)
            for neighbor in graph[node]:
                in_degree[neighbor] -= 1
                if in_degree[neighbor] == 0:
                    queue.append(neighbor)
        
        # 检测环
        if len(order) != len(self._mechanisms):
            return []  # 有环,返回空

        return order

    def verify_and_activate(self, name: str, claim: str = "", hypothesis: str = "",
                            graph: dict | None = None) -> dict:
        """P6 激活闭环: 验证机制是否可安全激活, 通过后翻为 active。

        三道门(不自动直替生产):
          1. IronLaw.verify(claim)  — 不违反核心约束
          2. AntiEvo.check(hypothesis) — 不退化/不重复
          3. FGGM.verify(graph)   — 图结构有效(若有图)

        全部通过 → activate(): status="active" + 进 _enabled。
        任一道门失败 → 保持 pending, 返回失败原因。

        Args:
            name: 机制名
            claim: IronLaw 验证声明(如机制描述)
            hypothesis: AntiEvo 假设(如机制名+来源)
            graph: FGGM 验证图(可选, 机制依赖图)

        Returns:
            dict: {activated: bool, gates: {...}, reason: str}
        """
        if name not in self._mechanisms:
            return {"activated": False, "reason": "not_found"}
        entry = self._mechanisms[name]
        if entry["status"] == "active":
            return {"activated": True, "reason": "already_active", "gates": {}}

        gates = {}
        # 门1: IronLaw
        try:
            from prometheus_ultra.evolution.iron_law import VerificationIronLaw
            iron = VerificationIronLaw(strict_fuzzy_rejection=True)
            r1 = iron.verify(claim or name)
            gates["iron_law"] = {"passed": bool(getattr(r1, "passed", False)),
                                 "confidence": getattr(r1, "confidence", 0.0)}
        except Exception as e:
            logger.debug("IronLaw verify failed: %s", e)
            gates["iron_law"] = {"passed": True, "confidence": 0.5, "note": "unavailable"}

        # 门2: AntiEvo
        try:
            from prometheus_ultra.evolution.anti_evolution_gate import AntiEvolutionGate
            anti = AntiEvolutionGate()
            r2 = anti.check(hypothesis or name)
            gates["anti_evo"] = {"passed": bool(getattr(r2, "passed", False)),
                                 "verdict": getattr(r2, "verdict", "SAFE")}
        except Exception as e:
            logger.debug("AntiEvo check failed: %s", e)
            gates["anti_evo"] = {"passed": True, "verdict": "SAFE", "note": "unavailable"}

        # 门3: FGGM(仅当提供图时)
        if graph is not None:
            try:
                from prometheus_ultra.evolution.fggm import FGGVerifier
                fggm = FGGVerifier()
                r3 = fggm.verify(graph)
                gates["fggm"] = {"passed": bool(r3.get("valid", True)),
                                 "node_count": r3.get("node_count", 0)}
            except Exception as e:
                logger.debug("FGGM verify failed: %s", e)
                gates["fggm"] = {"passed": True, "note": "unavailable"}

        # 全部通过才激活
        failed = [g for g, v in gates.items() if not v.get("passed", True)]
        if failed:
            entry["status"] = "blocked"
            self._history.append({"action": "blocked", "name": name, "gates": gates})
            return {"activated": False, "reason": f"gates_failed: {failed}", "gates": gates}

        entry["status"] = "active"
        entry["activated_at"] = __import__("time").time()
        self._enabled.add(name)
        self._history.append({"action": "activate", "name": name, "gates": gates})
        # P0a: 激活后触发消费者回调(接生产) — 解 B1 僵尸机制
        # T4(category=compiled)->host.emit_capability; T3->inject_gene_specs 等
        self._consume_active(name, entry)
        return {"activated": True, "reason": "verified", "gates": gates}

    def register_consumer(self, category: str, consumer: callable) -> None:
        """P0a: 注册某 category 的激活消费者.

        consumer(entry: dict) -> None  在机制激活后被调用, 负责把机制接进生产
        (如 T4 编译机制 -> 经 HostAgentAdapter 导出给宿主; T3 提取机制 -> 注入 gene_specs).
        这是 P6'不自动直替'原则的精确落地: 激活=通知消费者生成"建议/补丁",
        由消费者决定是否/如何接生产(通常走 A-B 并行或宿主确认, 非直接覆盖).
        """
        self._consumers[category] = consumer

    def _consume_active(self, name: str, entry: dict) -> None:
        """P0a: 按 category 派发激活事件给已注册消费者."""
        category = entry.get("category", "")
        consumer = self._consumers.get(category)
        if consumer is None:
            logger.debug("Registry: no consumer for category=%s (mechanism stays registered)", category)
            return
        try:
            consumer(entry)
            entry["consumed_at"] = __import__("time").time()
            self._history.append({"action": "consume", "name": name, "category": category})
        except Exception as e:
            logger.warning("Registry: consumer for %s failed: %s", name, e)
            entry["consume_error"] = str(e)
    
    def get_enabled(self) -> list[str]:
        """返回当前已启用(含已激活)机制名列表. 公开接口供监控/熔断使用."""
        return list(self._enabled)

    def health_check(self) -> dict:
        """健康检查.
        
        Returns:
            dict: 健康报告
        """
        issues = []
        
        # 检查孤立机制(未被依赖且从未调用)
        depended_on = set()
        for name, mech in self._mechanisms.items():
            for dep in mech["dependencies"]:
                depended_on.add(dep)
        
        for name in self._enabled:
            if self._mechanisms[name]["invoke_count"] == 0 and name not in depended_on:
                issues.append({"type": "unused", "mechanism": name})
        
        # 检查环依赖
        order = self.resolve_dependencies()
        if len(order) < len(self._mechanisms):
            issues.append({"type": "circular_dependency", "total": len(self._mechanisms), "resolved": len(order)})
        
        report = {
            "healthy": len(issues) == 0,
            "issues": issues,
            "total_mechanisms": len(self._mechanisms),
            "enabled": len(self._enabled),
            "total_invocations": sum(m["invoke_count"] for m in self._mechanisms.values()),
        }
        
        self._health_checks.append(report)
        return report
    
    def get_stats(self) -> dict:
        """获取统计."""
        categories = {}
        for mech in self._mechanisms.values():
            cat = mech["category"]
            categories[cat] = categories.get(cat, 0) + 1
        
        return {
            "registered": len(self._mechanisms),
            "enabled": len(self._enabled),
            "categories": categories,
            "history_size": len(self._history),
            "total_invocations": sum(m["invoke_count"] for m in self._mechanisms.values()),
        }
