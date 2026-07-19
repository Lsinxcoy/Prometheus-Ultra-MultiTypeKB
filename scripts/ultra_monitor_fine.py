#!/usr/bin/env python
"""Ultra 最细粒度运行监控 (每30min) — 纯监控, 不驱动系统.

设计原则(对齐用户'颗粒度最细'要求):
- 数据来源: /api/v1/monitor/detail (Nexus 单机制级 + 系统指标 + 管道统计)
- 最细粒度: 单机制 invoke_count/effect/error_count/status/last_invoked
  + 沉默机制 + 路由接管 + 动态层 + 突触修剪 + 系统资源 + 管道 runs/failures
- 纯监控: 只读, 不 POST 生命周期(不人为制造流量, 看真实运行)
- 每30min 一轮, 后台常驻; 每轮发飞书

运行: python scripts/ultra_monitor_fine.py  (后台; 或 nohup)
依赖: 系统已跑 (api_server :9200)
"""
import sys, os, json, time, pathlib, datetime, urllib.request, urllib.error

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
API = os.environ.get("ULTRA_API", "http://127.0.0.1:9200")
PROXY = os.environ.get("ULTRA_PROXY", "http://127.0.0.1:7890")
os.environ.setdefault("HTTPS_PROXY", PROXY)
os.environ.setdefault("HTTP_PROXY", PROXY)
INTERVAL = int(os.environ.get("ULTRA_MON_INTERVAL", "1800"))  # 30min


def call(path, timeout=30):
    try:
        req = urllib.request.Request(API + path)
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return {"_error": f"HTTP {e.code}: {e.read().decode()[:200]}"}
    except Exception as e:
        return {"_error": str(e)[:200]}


def build_report(detail: dict) -> str:
    """把最细粒度 detail 压成飞书可读文本(单机制级)."""
    snap = detail.get("snapshot", {})
    mechs = detail.get("mechanisms", {})
    pipes = detail.get("pipelines", {})
    sys_m = detail.get("system", {})
    now = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    L = [f"🔬 Ultra 最细监控 {now}", ""]

    # —— 系统资源 ——
    L.append("【系统资源】")
    if sys_m:
        for k in ("cpu_percent", "memory_percent", "memory_used_mb", "memory_available_mb",
                  "disk_percent", "process_memory_mb", "thread_count"):
            if k in sys_m:
                L.append(f"  {k}: {sys_m[k]}")
    else:
        L.append("  (无系统指标)")

    # —— 总体 ——
    L.append("")
    L.append("【总体】")
    L.append(f"  机制总数: {snap.get('mechanisms')}  已消费: {snap.get('consumed')}  "
             f"消费率: {round(snap.get('rate',0),3)}")
    L.append(f"  总调用: {detail.get('total_invocations')}  动态层: {snap.get('dynamic')}  "
             f"基本盘: {snap.get('base')}")
    L.append(f"  路由接管: {len(snap.get('route_overrides',{}))}  "
             f"突触修剪(禁用): {len(snap.get('pruned_disabled',[]))}")

    # —— 管道健康 ——
    L.append("")
    L.append("【7管道健康】")
    for pn, pv in sorted(pipes.items()):
        runs, fails = pv.get("runs", 0), pv.get("failures", 0)
        rate = (runs - fails) / runs if runs else 1.0
        flag = "✅" if (fails == 0 and runs > 0) or runs == 0 else "⚠️"
        L.append(f"  {flag} {pn}: runs={runs} fail={fails} 成功率={round(rate,3)}")

    # —— 单机制级: 高频 Top10 ——
    L.append("")
    L.append("【机制调用 Top10】")
    top = sorted(mechs.items(), key=lambda kv: kv[1].get("invoke_count", 0), reverse=True)[:10]
    for n, m in top:
        L.append(f"  {n}: inv={m['invoke_count']} err={m['error_count']} "
                 f"eff={m['effect']} cat={m['category']} st={m['status']}")

    # —— 错误机制 ——
    errs = [(n, m) for n, m in mechs.items() if m.get("error_count", 0) > 0]
    if errs:
        L.append("")
        L.append(f"【⚠️ 错误机制 {len(errs)}】")
        for n, m in sorted(errs, key=lambda kv: kv[1]["error_count"], reverse=True)[:10]:
            L.append(f"  {n}: err={m['error_count']} inv={m['invoke_count']} st={m['status']}")

    # —— 沉默机制(已注册从未调用) ——
    silent = snap.get("silent_mechanisms", [])
    if silent:
        L.append("")
        L.append(f"【😴 沉默机制 {len(silent)}】 (注册但 invoke=0)")
        L.append("  " + ", ".join(silent[:20]))
        if len(silent) > 20:
            L.append(f"  ... 另 {len(silent)-20} 个")

    # —— 路由接管中 ——
    ro = snap.get("route_overrides", {})
    if ro:
        L.append("")
        L.append(f"【🔀 路由接管 {len(ro)}】")
        for base, dyn in ro.items():
            L.append(f"  {base} -> {dyn}")

    # —— 动态层 ——
    ad = snap.get("active_dynamic", [])
    if ad:
        L.append("")
        L.append(f"【🌱 动态接管中 {len(ad)}】")
        L.append("  " + ", ".join(ad[:15]))

    return "\n".join(L)


def send_feishu(text: str) -> bool:
    secret_path = pathlib.Path(REPO) / "feishu_secret.json"
    if not secret_path.exists():
        print("[WARN] feishu_secret.json 不存在, 跳过飞书发送")
        print(text)
        return False
    try:
        cfg = json.loads(secret_path.read_text(encoding="utf-8"))
        app_id, app_secret, chat_id = cfg["app_id"], cfg["app_secret"], cfg["chat_id"]
    except Exception as e:
        print(f"[ERR] 读凭据失败: {e}")
        return False
    # token
    try:
        tok_req = urllib.request.Request(
            "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal",
            data=json.dumps({"app_id": app_id, "app_secret": app_secret}).encode(),
            headers={"Content-Type": "application/json"}, method="POST")
        with urllib.request.urlopen(tok_req, timeout=15) as r:
            tok = json.loads(r.read().decode())
        if tok.get("code") != 0:
            print(f"[ERR] token 失败: {tok}")
            return False
        token = tok["tenant_access_token"]
    except Exception as e:
        print(f"[ERR] token 异常: {e}")
        return False
    # send
    try:
        msg_req = urllib.request.Request(
            "https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=chat_id",
            data=json.dumps({
                "receive_id": chat_id, "msg_type": "text",
                "content": json.dumps({"text": text}),
            }).encode(),
            headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
            method="POST")
        with urllib.request.urlopen(msg_req, timeout=15) as r:
            res = json.loads(r.read().decode())
        if res.get("code") == 0:
            print(f"[OK] 飞书发送成功 {datetime.datetime.now()}")
            return True
        print(f"[ERR] 发送失败: {res}")
        return False
    except Exception as e:
        print(f"[ERR] 发送异常: {e}")
        return False


def tick():
    """一轮监控: 拉最细数据 + 发飞书."""
    detail = call("/api/v1/monitor/detail")
    if "_error" in detail:
        msg = f"⚠️ Ultra 监控取数失败: {detail['_error']}\nAPI={API}\n请检查系统是否在跑"
        print(msg)
        send_feishu(msg)
        return False
    text = build_report(detail)
    send_feishu(text)
    # 落盘备查
    try:
        out = pathlib.Path(REPO) / "monitor_fine_latest.json"
        out.write_text(json.dumps(detail, ensure_ascii=False, indent=1), encoding="utf-8")
    except Exception:
        pass
    return True


if __name__ == "__main__":
    print(f"[启动] Ultra 最细监控 每 {INTERVAL}s (API={API})")
    # 首轮立即跑
    tick()
    while True:
        time.sleep(INTERVAL)
        try:
            tick()
        except Exception as e:
            print(f"[ERR] tick 异常: {e}")
