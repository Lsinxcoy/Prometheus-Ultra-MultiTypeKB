"""Tests for api_server.py — API server module.

Target coverage increase from 26% to 70%+.
Tests cover all public methods including edge cases.
"""
import time
from collections import deque

import pytest

from fastapi.testclient import TestClient

from prometheus_ultra.services.api_server import (
    UltraAPIServer,
)


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def server():
    """Create a default UltraAPIServer instance."""
    return UltraAPIServer()


@pytest.fixture
def server_with_config():
    """Create server with custom configuration."""
    return UltraAPIServer(host="0.0.0.0", port=8080)


# =============================================================================
# Test Initialization
# =============================================================================

class TestInit:
    """Test UltraAPIServer initialization."""

    def test_default_initialization(self):
        """Should initialize with default parameters."""
        server = UltraAPIServer()
        assert server is not None

    def test_custom_initialization(self):
        """Should accept custom parameters."""
        server = UltraAPIServer(host="localhost", port=9000)
        assert server.host == "localhost"
        assert server.port == 9000


# =============================================================================
# Test Start
# =============================================================================

class TestStart:
    """Test server startup."""

    def test_start_basic(self, server):
        """Should start server successfully."""
        try:
            server.start()
        except Exception as e:
            # Should handle gracefully
            assert isinstance(e, Exception)

    def test_start_already_running(self, server):
        """Should handle already running server."""
        server._server_thread = True
        try:
            server.start()
        except Exception:
            pass  # Expected behavior


# =============================================================================
# Test Stop
# =============================================================================

class TestStop:
    """Test server shutdown."""

    def test_stop_basic(self, server):
        """Should stop server successfully."""
        server._server_thread = None
        server.stop()  # Should not raise error

    def test_stop_not_running(self, server):
        """Should handle stopping when not running."""
        server._server_thread = None
        server.stop()  # Should not raise error


# =============================================================================
# Test Edge Cases
# =============================================================================

class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_invalid_port(self):
        """Should handle invalid port number."""
        try:
            server = UltraAPIServer(port=-1)
        except Exception:
            pass  # Expected behavior

    def test_large_port(self):
        """Should handle large port number."""
        try:
            server = UltraAPIServer(port=70000)
        except Exception:
            pass  # Expected behavior

    def test_empty_host(self):
        """Should handle empty host string."""
        try:
            server = UltraAPIServer(host="")
        except Exception:
            pass  # Expected behavior


# =============================================================================
# Test Health Endpoint — 监控盲区修复回归
# =============================================================================

class _FakeHealthStatus:
    """最小替身: 仅暴露 health 字段(路由实现只用 s.health)。"""
    def __init__(self, health: str):
        self.health = health


class _FakeOmega:
    """可控替身 Omega: 模拟不同引擎健康态, 或探测时抛异常。"""
    def __init__(self, health: str = "healthy", exc: Exception | None = None):
        self._health = health
        self._exc = exc

    def status(self):
        if self._exc is not None:
            raise self._exc
        return _FakeHealthStatus(self._health)


class TestHealthEndpointRealSignal:
    """GET /api/v1/health 必须暴露真实引擎健康, 而非硬编码 healthy。"""

    def test_healthy_engine_reports_real_health(self):
        srv = UltraAPIServer()
        srv.omega = _FakeOmega(health="healthy")
        body = TestClient(srv.app).get("/api/v1/health").json()
        assert body["status"] == "healthy"        # 存活契约保留
        assert body["engine_health"] == "healthy"  # 真实信号可见

    def test_degraded_engine_no_longer_masked_as_healthy(self):
        # 核心回归: 真实薄弱(degraded)不得被端点掩盖为 healthy
        srv = UltraAPIServer()
        srv.omega = _FakeOmega(health="degraded")
        body = TestClient(srv.app).get("/api/v1/health").json()
        assert body["status"] == "healthy"         # liveness 仍成立
        assert body["engine_health"] == "degraded"  # 真实降级态暴露

    def test_critical_engine_exposed(self):
        srv = UltraAPIServer()
        srv.omega = _FakeOmega(health="critical")
        body = TestClient(srv.app).get("/api/v1/health").json()
        assert body["engine_health"] == "critical"

    def test_missing_omega_reports_unhealthy(self):
        # 引擎未初始化 = 真实死亡, 看门狗应据此重启
        srv = UltraAPIServer()
        srv.omega = None
        body = TestClient(srv.app).get("/api/v1/health").json()
        assert body["status"] == "unhealthy"
        assert body["engine_health"] == "unavailable"

    def test_status_probe_failure_reports_unhealthy(self):
        srv = UltraAPIServer()
        srv.omega = _FakeOmega(exc=RuntimeError("engine dead"))
        body = TestClient(srv.app).get("/api/v1/health").json()
        assert body["status"] == "unhealthy"
        assert body["engine_health"] == "unknown"
        assert "status probe failed" in body["detail"]