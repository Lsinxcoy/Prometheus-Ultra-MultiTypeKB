"""Pytest 全局配置: 隔离 Omega 的 store db, 避免测试间共享 prometheus_memory.db 污染。

每个 Omega() 实例用独立临时文件数据库, 消除测试顺序/累积导致的
sqlite3 冲突与状态污染(全量跑 60+ 文件时尤为明显)。

注意: 不能用 :memory: —— SQLite 的 :memory: 每个连接独立, 而 MinervaStore
内部某些路径可能复用/新建连接, 导致写入不可见。临时文件 db 则无此问题。
"""
import os
import tempfile

import pytest


@pytest.fixture(autouse=True)
def _isolate_store_db(monkeypatch):
    """让 Omega 默认 db 指向独立临时文件, 每个测试隔离。"""
    import prometheus_ultra.life as life_mod
    orig_init = life_mod.Omega.__init__

    _counter = {"n": 0}

    def _patched_init(self, config=None, db_path=None, *a, **kw):
        if db_path is None:
            _counter["n"] += 1
            tmp = tempfile.gettempdir()
            db_path = os.path.join(tmp, f"ultra_test_db_{os.getpid()}_{_counter['n']}.db")
        return orig_init(self, config, db_path, *a, **kw)

    monkeypatch.setattr(life_mod.Omega, "__init__", _patched_init)


def pytest_collection_modifyitems(config, items):
    """集成 server 测试需外部/真实 server, 无 RUN_SERVER_TESTS 环境变量时跳过。

    原因: test_hermes_integration 要求手动启动外部 API server(端口9200);
    test_api_server 的 TestStart/TestStop 启动真实 uvicorn, 端口占用时
    线程内 sys.exit(1) 成为未处理异常, 污染后续所有测试(已实测复现:
    test_api_server 之后紧跟的纯单元测试被连带标记失败)。

    单元 E2E 套件不该包含这些集成测试。需要验证 server 时:
        RUN_SERVER_TESTS=1 pytest tests/test_api_server.py tests/test_hermes_integration.py
    """
    if os.environ.get("RUN_SERVER_TESTS") == "1":
        return
    skip_server = pytest.mark.skip(
        reason="集成 server 测试需 RUN_SERVER_TESTS=1 且外部/真实 server 可用"
    )
    for item in items:
        path = item.nodeid
        if "test_hermes_integration.py" in path:
            item.add_marker(skip_server)
        elif "test_api_server.py" in path and (
            "TestStart" in path or "TestStop" in path
        ):
            item.add_marker(skip_server)
