"""自己重新审计当前代码: 不依赖历史文档, 直接看每个机制文件的实现特征.

方法: 对 audit 点名的机制, 检查其实现是否真有算法逻辑, 还是硬编码/mock.
重点查 MOCK 级 13 个 + 几个 DEGRADED 代表.

判定规则(基于代码特征, 非记忆):
- MOCK 特征: 返回硬编码字符串/随机扰动/空列表默认/无真实算法
- DEGRADED 特征: 有算法但简化(如 Jaccard 替代 embedding)
- WORKING 特征: 真算法(RK4/GA/tournament/真实HTTP等)
"""
import sys, os, re
sys.path.insert(0, "E:/Prometheus-Ultra-MultiTypeKB/src")
os.chdir("E:/Prometheus-Ultra-MultiTypeKB")

TARGETS = [
    # (文件, 关注的函数/类)
    ("src/prometheus_ultra/learning/deep_retrofit_6.py", "deep_retrofit_6"),
    ("src/prometheus_ultra/evolution/reasoning_bank.py", "reasoning_bank"),
    ("src/prometheus_ultra/evolution/openspace.py", "openspace"),
    ("src/prometheus_ultra/learning/five_step.py", "five_step"),
    ("src/prometheus_ultra/evolution/fggm.py", "fggm"),
    ("src/prometheus_ultra/ecosystem/speculative_fork.py", "speculative_fork"),
    ("src/prometheus_ultra/governance/autonomy.py", "evolution_grill"),
    ("src/prometheus_ultra/evolution/everos.py", "everos"),
    ("src/prometheus_ultra/evolution/memento.py", "memento"),
    ("src/prometheus_ultra/learning/deep_retrofit.py", "deep_retrofit"),
    ("src/prometheus_ultra/evolution/coevolve.py", "coevolve"),
    ("src/prometheus_ultra/evolution/speculative.py", "speculative"),
    ("src/prometheus_ultra/loop/semantic_early_stopping.py", "semantic_early_stopping"),
    ("src/prometheus_ultra/evaluation/harness.py", "harness_x"),
    ("src/prometheus_ultra/learning/knowledge_to_mechanism.py", "knowledge_to_mechanism"),
    ("src/prometheus_ultra/evolution/eval_driven.py", "eval_engine"),
    ("src/prometheus_ultra/ecosystem/lotka_volterra.py", "lotka_volterra"),
    ("src/prometheus_ultra/ecosystem/edre.py", "edre"),
    ("src/prometheus_ultra/learning/scanner.py", "knowledge_scanner"),
]

def analyze(path, name):
    try:
        src = open(path, encoding="utf-8").read()
    except FileNotFoundError:
        return f"[文件不存在] {path}"
    lines = src.split("\n")
    n = len(lines)
    # 特征检测
    has_random_gauss = bool(re.search(r"random\.gauss|random\.random\(\)\s*\*\s*[0-9]|randrange", src))
    has_hardcoded_return = len(re.findall(r"return\s+[\"'""][^\"'""]{20,}", src))  # 长字符串字面返回
    has_real_algo = bool(re.search(r"RK4|runge|tournament|crossver|crossover|def evolve|def replicate|replicator|gradient|embedding|requests\.|urllib|http", src, re.I))
    has_pass_only = bool(re.search(r"def \w+\(.*\):\s*\n\s*(return|pass)\s", src))
    # 文件大小(行数)作为实现复杂度 proxy
    return (f"{name:22s} | {n:4d}行 | gauss={has_random_gauss} hardstr={has_hardcoded_return>0} "
            f"realalgo={has_real_algo} | 特征: " +
            ("MOCK嫌疑" if (has_random_gauss and not has_real_algo and n<120) or (has_hardcoded_return and not has_real_algo) else "需细看"))

for path, name in TARGETS:
    print(analyze(path, name))
