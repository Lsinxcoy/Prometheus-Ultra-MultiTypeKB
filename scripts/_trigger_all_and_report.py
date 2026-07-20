#!/usr/bin/env python
"""一次性: 触发全部管道 (产生真实产出) + 立即发产出视角运行报告."""
import json, time, urllib.request, urllib.error, sys, os

API = "http://127.0.0.1:9200"

def post(path, payload):
    data = json.dumps(payload).encode()
    req = urllib.request.Request(API + path, data=data,
                                  headers={"Content-Type": "application/json"}, method="POST")
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"_error": f"HTTP {e.code}: {e.read().decode()[:200]}"}
    except Exception as e:
        return {"_error": str(e)[:200]}

# 触发全部 7 管道 + T4 编译端点
results = {}
results["recall"] = post("/api/v1/recall", {"query": "neural architecture search", "limit": 5})
results["learn"] = post("/api/v1/learn", {"source": "arxiv", "query": "self-evolving AI agent", "max_results": 3})
results["reflect"] = post("/api/v1/reflect", {"context": "periodic full-cycle run"})
results["dream"] = post("/api/v1/dream", {"branch": "main"})
results["evolve"] = post("/api/v1/evolve", {"context": "improve memory consolidation", "branch": "main", "confidence": 0.6})
results["maintain"] = post("/api/v1/maintain", {})
results["remember"] = post("/api/v1/remember", {"content": "全管道运行报告触发: Ultra 系统自检产出", "utility": 0.8, "tags": ["selfcheck"]})
results["t4_compile"] = post("/api/v1/t4/compile", {})

# 汇总管道触发结果
print("=== 管道触发结果 ===")
for name, r in results.items():
    if "_error" in r:
        print(f"  {name}: ERROR {r['_error']}")
    else:
        ok = r.get("success")
        data = r.get("data", {})
        print(f"  {name}: success={ok} data_keys={list(data.keys())[:4]}")

# 立即发产出视角运行报告
sys.path.insert(0, os.path.dirname(__file__))
import ultra_monitor_fine as m
ok = m.tick()
print("REPORT SENT:", ok)
