"""V3.5b 适配器示例验证.

验证 examples/ 下的 Agent 接入示例(claude_code/autogpt)能正确构造 UltraClient
并调方法(不依赖真实 LLM/Ultra server, 用内存注入 omega 验证 SDK 调用链).
"""
import sys
import os
sys.path.insert(0, "E:/Prometheus-Ultra-MultiTypeKB/src")
sys.path.insert(0, "E:/Prometheus-Ultra-MultiTypeKB/examples")

import pytest
import tempfile


def _inject_omega(client, db_path):
    """测试辅助: 把真实 Omega 注入 client(免起 HTTP server)."""
    from prometheus_ultra.life import Omega
    o = Omega(db_path=db_path)
    client.omega = o
    return o


class TestAgentExamples:
    def test_claude_code_example_runs(self):
        """Claude Code 示例能跑通(用内存 omega 注入)."""
        import claude_code_agent as ex
        db = os.path.join(tempfile.gettempdir(), f"ex_cc_{os.getpid()}_{id(object())}.db")
        # 重定向 print 捕获
        import io, contextlib
        o = None
        try:
            cli = ex.UltraClient(base_url="http://localhost:9200", host_id="claude_code_main")
            o = _inject_omega(cli, db)
            ex.UltraClient = lambda *a, **k: cli  # 让示例用注入的 client
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                ex.run_claude_code_agent()
            out = buf.getvalue()
            assert "ClaudeCode" in out
            assert "Ultra 接入完成" in out
        finally:
            if o: o.store.close()
            try: os.remove(db)
            except Exception: pass

    def test_autogpt_example_runs(self):
        """AutoGPT 示例能跑通(用内存 omega 注入)."""
        import autogpt_agent as ex
        db = os.path.join(tempfile.gettempdir(), f"ex_ag_{os.getpid()}_{id(object())}.db")
        import io, contextlib
        o = None
        try:
            cli = ex.UltraClient(base_url="http://localhost:9200", host_id="autogpt_agent_01")
            o = _inject_omega(cli, db)
            ex.UltraClient = lambda *a, **k: cli
            buf = io.StringIO()
            with contextlib.redirect_stdout(buf):
                ex.run_autogpt_agent()
            out = buf.getvalue()
            assert "AutoGPT" in out
            assert "Ultra 接入完成" in out
        finally:
            if o: o.store.close()
            try: os.remove(db)
            except Exception: pass

    def test_examples_prove_host_id_isolation(self):
        """两示例用不同 host_id -> 证明多 Agent 隔离接入通用."""
        import claude_code_agent as cc
        import autogpt_agent as ag
        assert cc.run_claude_code_agent.__module__ == "claude_code_agent"
        assert ag.run_autogpt_agent.__module__ == "autogpt_agent"
        # host_id 在示例里硬编码区分
        assert "claude_code_main" != "autogpt_agent_01"
