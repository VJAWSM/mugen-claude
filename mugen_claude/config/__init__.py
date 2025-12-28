"""
Configuration module for Mugen Claude.
"""
from .settings import Settings
from .agents import AgentDefinition, AGENT_DEFINITIONS, get_agent_definition, register_agent_definition

__all__ = [
    'Settings',
    'AgentDefinition',
    'AGENT_DEFINITIONS',
    'get_agent_definition',
    'register_agent_definition',
]
