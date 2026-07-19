"""9200 看门狗: 消除 cron 重启真空窗.

循环检测 9200 是否可达, 不可达(真空窗/崩溃)时自动拉起 api_server.
配合 cron 的 30m 循环使用, 但本脚本提供秒级兜底(避免最长 30m 真空).

用法(后台常驻):
  python watchdog_9200.py
或注册为 Windows 任务计划程序 / cron 每分钟.
"""
import socket, subprocess, sys, time, os

PORT = 9200
HOST = "127.0.0.1"
DB = os.path.join(os.path.dirname(__file__), "src", "prometheus_ultra.db")
CHECK_INTERVAL = 10  # 秒
START_GUARD = 3     # 启动后等待秒


def is_up():
    try:
        with socket.create_connection((HOST, PORT), timeout=3):
            return True
    except OSError:
        return False


def launch():
    return subprocess.Popen(
        [sys.executable, "-m", "prometheus_ultra.services.api_server",
         "--db-path", DB, "--host", HOST, "--port", str(PORT)],
        cwd=os.path.dirname(__file__),
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )


def main():
    print(f"[watchdog] 启动, 每 {CHECK_INTERVAL}s 检测 {HOST}:{PORT}")
    proc = None
    while True:
        if not is_up():
            print(f"[watchdog] {HOST}:{PORT} 不可达, 拉起 api_server...")
            try:
                if proc and proc.poll() is None:
                    proc.kill()
            except Exception:
                pass
            proc = launch()
            time.sleep(START_GUARD)
            if is_up():
                print("[watchdog] api_server 已恢复")
            else:
                print("[watchdog] 拉起后仍不可达, 下轮重试")
        time.sleep(CHECK_INTERVAL)


if __name__ == "__main__":
    main()
