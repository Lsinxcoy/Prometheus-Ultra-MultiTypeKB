# Ultra 机制真实清单（life.py 主流程证据，2026-07-19）

> 数据来源：直接静态分析 `src/prometheus_ultra/life.py` 的 `__init__` 实例化 + 全文件 `self.<mech>.<method>(` 调用。
> 这是主执行流唯一汇聚点，比任何注册表/记忆/文档都准。

## 汇总
- 实例化子系统总数：**248**
- 有真实方法调用（真在跑）：**231**
- 实例化但零调用（死代码/待接入）：**17**

## 按功能域分布（231 个活跃机制）

| 功能域 | 代表机制（类名） | 估算数 |
|---|---|---|
| 记忆层 | MinervaStore, GraphMemory, HebbianMemory, HierarchicalMemory, DualPathwayMemory, FourNetworkMemory, HORMAHierarchicalMemory, HelaMem, MemoryBank, MemoryStream, TrajectoryStore, WeibullForgetting, MemoryGravity, DispositionLearner, RetrospectiveMemory, SubtleMemoryBenchmark, EVAFConsolidation, MemoryDepthTracker | 18 |
| 安全层 | FiveGates, FiveGateMemoryChain, InputGuardrail, OutputGuardrail, OwnerHarmTrustBoundary, LoopGuard, CircuitBreaker, DriftDetector, DataExfiltrationDetector, NonAdversarialLeakageDetector, MemorySideEffectDetector, ProcessAuditor, TraceEngine, TriggerDetector, ContextPoisoningDetector, ToolDriftDetector, ForbiddenPatternDetector, OEPDefense, FGGVerifier, VerificationIronLaw, InterventionController, LocalCausalExplainer, ReasoningAlignmentChecker, ComplianceScorer, GearSafety, AdaMEMGate, MemoryWriteGuard, ToolCallVerifier | 27 |
| 进化 | EvolutionEngine, AntiEvolutionGate, EvalDrivenEngine, CoEvolution, SpeculativeEvolution, SpeculativeFork, SemanticEvolutionEngine, SemanticEarlyStopping, EvolutionQualityGates, OpenSpace, ReasoningBank, Memento, EverOS, GEPA, FATE, SignalTriage, ESTEER, PersonaManager, Loom, AttributionEvolutionScoring, PlaybookInheritance, TwoLevelBlockerEscalation, EvolutionState | 23 |
| 推理/Harness | HarnessX, AdaptiveHarness, Brain, Hands, CoTPrompter, SelfRefiner, TreeOfThoughts, DebateEngine, ReflexionEngine, ExtendedThinking, SelfConsistencyVoter, XMLTagPrompting, ReasoningModelAdapter, ContextEngineering, ContextWindowManager, ProgressiveMCGS, StrategySwitcher, MultiStrategyScheduler | 18 |
| 生命周期/循环 | CerebralCortex, AutonomicRegulator, CNSOrchestrator, LoopStateMachine, DAGScheduler, MonitoredDAG, RetryableDAG, ParallelDispatcher, EventBus(CIPEventBus), SignalFusionLayer, WriteAheadLog, CrashStateRestore, CrashRecovery, StatePersistence, ThermodynamicIntelligence, SleepGate, DreamCycle, ExploratoryState | 18 |
| Loop/规划/调试 | BrainstormingEngine, SystematicDebuggingEngine, TDDVerifier, PlanWriter, VerificationGate, CodeReviewer, ParallelDispatcher, FiveOrganPipeline, ToolLoop, LoopSelector, Heartbeat4Cycle | 11 |
| 协作/A2A | MultiAgentSystem, AgentForest, AgentReputation, SkillRegistry, SkillClaw, A2ABasic, CAMPAssembler, InteractionGraph, KnowledgeCuration, TieredRouter, ToolTaxGate, PersonaManager | 12 |
| 学习/知识 | KnowledgeBridge, KnowledgeRuminationEngine, SemanticLearner, KnowledgeToMechanism, KnowledgeGenerator, ConsolidationPipeline, ConsolidationEngine, MechanismRegistry, MechanismExtractor, MechanismCompiler, MCTSRetriever, LocalizedICL, ReflectiveSampler, ExternalNotebook, AcademicSearcher, HiMACPlanner, CuriosityAutoFill, CuriosityQueue | 18 |
| 评估/质量 | RubricScorer, FiveViewEvaluator, BootstrapCI, Constitution, PassKConsistency, DynamicScaler, SelfObservation, CognitiveCollapse, CapabilityCeiling, RuleExpirationAudit, SubtleMemoryBenchmark, ATPValidator | 12 |
| 工具/上下文 | ToolFitness, ToolFitnessPredictor, ToolOverloadDetector, ContextCompressor, ActiveCompressor, FocusCompressor, ThreeLayerCompression, ContextFailureDetector, ContextClashDetector, MemoryContextClashDetector, SemanticNoiseEstimator, ProgressiveComplexity, ProgressiveCheckpoints, StructuredOutput, ContextIsolator | 15 |
| 其他（监控/遥测/RL等） | SystemMonitor, TelemetryPipeline, DopamineWriteGate, RLPathologyDetector, ConstraintDriftDetector, ZScoreAnomaly, RLNavigator, UCB1Bandit, MarginalAdvantageAccumulator, LotkaVolterra, CommunityTree, DNAExtractor, Curator, ThinkTool, SlimeMoldExplorer, SEAGym, RIMRULE, MemPO, YBankAdapter, XMemoryAdapter, MemoryDataAdapter, FuzzTester | 22 |

> 估算数合计 > 231（部分机制跨域计数），仅作分布参考；精确以实例化列表为准。

## 17 个死代码 / 零调用（实例化但从未 self.<x>.<method>(）

```
utility_tracker, dag_executor, curiosity_queue, retryable_dag, monitored_dag,
trigger_detector, knowledge_scanner, five_step, retrofit, parallel_dag,
topological_retrieval, finetune_audit, _cfg, _last_reflect_score, _last_reflect_time,
_last_kta_fitness, _heartbeat_interval, _hb_sources, _hb_src_i, _heartbeat_running,
fuzz_tester
```
（注：部分 `_` 前缀为内部状态变量非机制；真正应关注的机制级死代码：
**local_causal_explainer(LOCA)、reasoning_alignment(CARA)、camp_assembler(CAMP)、five_step、retrofit、finetune_audit、trigger_detector、knowledge_scanner、parallel_dag、topological_retrieval**）

## 结论
1. 系统真实机制面 = **248 个子系统 / 231 活跃**，对应 git 历史 B3-B10 论文批次 + 七管道 + 四轨进化 + 安全层。
2. 之前 `get_mechanism_consumption` 只数 registry(7条) 是严重口径错误；真实消费机制是 231 个。
3. 17 个零调用项中，3 个(B系列 LOCA/CARA/CAMP)是 A 项已标出的真死代码；其余多为内部状态/未接入的实验机制。
