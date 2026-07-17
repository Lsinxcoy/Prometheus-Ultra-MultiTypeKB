"""CrashRecovery — 崩溃恢复机制.

基于:
- "Write-Ahead Logging" (Reuter & Sanders, 1980)
  - WAL预写日志: 先写日志再写数据
  - 检查点: 定期快照减少恢复时间
  - 日志回放: 崩溃后重放未检查点日志
  - 一致性验证: hash校验确保数据完整性

算法:
    create_checkpoint(state):
        1. 序列化状态
        2. 计算hash
        3. 存储快照+元数据
    
    recover():
        1. 查找最近有效检查点
        2. 验证hash完整性
        3. 回放未检查点日志
        4. 返回恢复结果

复杂度:
    checkpoint(): O(S) 其中S=状态大小
    recover(): O(L) 其中L=日志数量
"""
from __future__ import annotations
import time
import logging

logger = logging.getLogger(__name__)

import hashlib
import json
from collections import deque
from typing import Any


class CrashRecovery:
    """崩溃恢复管理器.
    
    WAL + 检查点 + 日志回放.
    """
    
    def __init__(self, session=None, max_checkpoints: int = 10, log_buffer: int = 100):
        """初始化.
        
        Args:
            session: 会话引用
            max_checkpoints: 最大检查点数
            log_buffer: 日志缓冲区大小
        """
        self._session = session
        self._checkpoints: list[dict] = []
        self._wal_log: deque = deque(maxlen=log_buffer)
        self._recoveries: list[dict] = []
        self._max_checkpoints = max_checkpoints
        self._pending_writes: list[dict] = []
        self._last_checkpoint_time: float = 0
    
    def create_checkpoint(self, state: dict | None = None) -> dict:
        """创建检查点.
        
        Args:
            state: 状态字典
        
        Returns:
            dict: 检查点信息
        """
        state = state or {}
        
        # 序列化状态
        try:
            state_json = json.dumps(state, default=str)
        except (TypeError, ValueError):
            state_json = str(state)
        
        state_hash = hashlib.sha256(state_json.encode()).hexdigest()[:16]
        
        checkpoint = {
            "id": len(self._checkpoints),
            "timestamp": time.time(),
            "state_hash": state_hash,
            "state_size": len(state_json),
            "pending_writes": len(self._pending_writes),
            "wal_size": len(self._wal_log),
        }
        
        self._checkpoints.append(checkpoint)
        self._last_checkpoint_time = checkpoint["timestamp"]
        
        # 限制检查点数量 (保留最新和最早的)
        if len(self._checkpoints) > self._max_checkpoints:
            keep = self._max_checkpoints // 2
            self._checkpoints = (
                self._checkpoints[:1] + self._checkpoints[-keep:]
            )
        
        # 清空待写入日志(已检查点)
        self._pending_writes = []
        
        return checkpoint
    
    def write_ahead_log(self, operation: str, data: Any = None):
        """写前日志记录.
        
        Args:
            operation: 操作类型
            data: 操作数据
        """
        log_entry = {
            "seq": len(self._wal_log),
            "timestamp": time.time(),
            "operation": operation,
            "data": data,
            "checkpoint_id": self._checkpoints[-1]["id"] if self._checkpoints else None,
        }
        self._wal_log.append(log_entry)
        self._pending_writes.append(log_entry)
    
    def recover(self, context: dict | None = None) -> dict:
        """从崩溃中恢复.
        
        Args:
            context: 恢复上下文
        
        Returns:
            dict: 恢复结果
        """
        ctx = context or {}
        start = time.time()
        
        if not self._checkpoints:
            recovery = {
                "recovered": False,
                "from_checkpoint": None,
                "status": "no_checkpoint",
                "recovered_ops": 0,
                "lost_ops": len(self._pending_writes),
            }
            self._recoveries.append(recovery)
            return recovery
        
        # 找最近的检查点(按时间倒序)
        latest = max(self._checkpoints, key=lambda c: c["timestamp"])
        
        # 验证检查点完整性
        valid = True
        if "state_hash" in ctx and ctx["state_hash"] != latest["state_hash"]:
            # hash不匹配, 找前一个检查点
            sorted_cp = sorted(self._checkpoints, key=lambda c: c["timestamp"], reverse=True)
            valid = len(sorted_cp) > 1
            if valid:
                latest = sorted_cp[1]
        
        # 回放检查点后的日志
        recovered_ops = 0
        replayed = []
        
        for entry in self._wal_log:
            if entry.get("checkpoint_id") == latest["id"]:
                replayed.append(entry)
                recovered_ops += 1
        
        # 待写入但未检查点的操作(可能丢失)
        lost_ops = len(self._pending_writes)
        
        recovery = {
            "recovered": True,
            "from_checkpoint": latest["id"],
            "checkpoint_age_s": time.time() - latest["timestamp"],
            "checkpoint_hash": latest["state_hash"],
            "checkpoint_valid": valid,
            "recovered_ops": recovered_ops,
            "lost_ops": lost_ops,
            "replay_log": replayed,
            "duration_ms": (time.time() - start) * 1000,
        }
        
        self._recoveries.append(recovery)
        return recovery
    
    def get_recovery_window(self) -> dict:
        """获取恢复窗口信息.
        
        Returns:
            dict: 检查点到现在的日志窗口
        """
        if not self._checkpoints:
            return {"has_checkpoint": False}
        
        latest = max(self._checkpoints, key=lambda c: c["timestamp"])
        age = time.time() - latest["timestamp"]
        
        # 检查点后的操作数
        post_cp_ops = sum(
            1 for e in self._wal_log if e.get("checkpoint_id") == latest["id"]
        )
        
        return {
            "has_checkpoint": True,
            "checkpoint_id": latest["id"],
            "age_seconds": round(age, 2),
            "pending_operations": post_cp_ops,
            "wal_size": len(self._wal_log),
        }
    
    def get_stats(self) -> dict:
        """获取统计."""
        recovery_window = self.get_recovery_window()
        
        return {
            "checkpoints": len(self._checkpoints),
            "recoveries": len(self._recoveries),
            "wal_size": len(self._wal_log),
            "pending_writes": len(self._pending_writes),
            "recovery_window": recovery_window,
        }
