"""
Coordination infrastructure for multi-agent orchestration.
"""
from .manager import CoordinationManager, AgentMessage, AgentStatus
from .file_lock import FileLock, file_lock

__all__ = [
    'CoordinationManager',
    'AgentMessage',
    'AgentStatus',
    'FileLock',
    'file_lock',
]
