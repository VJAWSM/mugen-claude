"""
Mugen Claude - Autonomous multi-agent orchestration system for Claude Code.
"""

__version__ = "0.1.0"
__author__ = "VJAWSM"

from .orchestrator import Orchestrator
from .coordination import CoordinationManager
from .agents import ExplorerAgent, PlannerAgent, ExecutorAgent

__all__ = [
    'Orchestrator',
    'CoordinationManager',
    'ExplorerAgent',
    'PlannerAgent',
    'ExecutorAgent',
]
