"""
Agent type definitions and configurations.
"""
from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class AgentDefinition:
    """Definition for an agent type."""
    name: str
    description: str
    capabilities: List[str]
    tools: List[str]  # Tools this agent can use
    system_prompt_template: str


# Pre-defined specialized agent types
AGENT_DEFINITIONS: Dict[str, AgentDefinition] = {
    "explorer": AgentDefinition(
        name="explorer",
        description="Explores codebases and gathers information",
        capabilities=["file_analysis", "pattern_search", "context_gathering"],
        tools=["read", "glob", "grep", "tree"],
        system_prompt_template="You are an expert code explorer..."
    ),

    "planner": AgentDefinition(
        name="planner",
        description="Creates implementation plans",
        capabilities=["planning", "task_breakdown", "architecture_design"],
        tools=["read", "query_explorer"],
        system_prompt_template="You are an expert system architect..."
    ),

    "executor": AgentDefinition(
        name="executor",
        description="Executes implementation tasks",
        capabilities=["code_writing", "file_modification", "testing"],
        tools=["read", "write", "edit", "bash"],
        system_prompt_template="You are an expert software developer..."
    ),

    # Specialized agent types (can be created dynamically)
    "java-agent": AgentDefinition(
        name="java-agent",
        description="Java development specialist",
        capabilities=["java_development", "maven", "gradle", "spring"],
        tools=["read", "write", "edit", "bash"],
        system_prompt_template="""You are an expert Java developer specializing in:
- Java best practices and design patterns
- Spring Framework and Spring Boot
- Maven and Gradle build systems
- JUnit testing
- Clean code and SOLID principles"""
    ),

    "python-agent": AgentDefinition(
        name="python-agent",
        description="Python development specialist",
        capabilities=["python_development", "pip", "pytest", "asyncio"],
        tools=["read", "write", "edit", "bash"],
        system_prompt_template="""You are an expert Python developer specializing in:
- Python best practices and PEP standards
- Async/await and asyncio
- Type hints and mypy
- pytest and testing
- Popular frameworks (Django, FastAPI, Flask)"""
    ),

    "frontend-agent": AgentDefinition(
        name="frontend-agent",
        description="Frontend development specialist",
        capabilities=["react", "vue", "typescript", "css", "webpack"],
        tools=["read", "write", "edit", "bash"],
        system_prompt_template="""You are an expert frontend developer specializing in:
- Modern JavaScript/TypeScript
- React, Vue, or Angular frameworks
- CSS and responsive design
- Webpack, Vite, and build tools
- Testing with Jest/Vitest"""
    ),

    "test-agent": AgentDefinition(
        name="test-agent",
        description="Testing and QA specialist",
        capabilities=["test_writing", "test_automation", "qa"],
        tools=["read", "write", "edit", "bash"],
        system_prompt_template="""You are an expert QA engineer specializing in:
- Unit, integration, and e2e testing
- Test-driven development (TDD)
- Testing frameworks and tools
- Code coverage analysis
- Test automation"""
    ),
}


def get_agent_definition(agent_type: str) -> AgentDefinition:
    """Get agent definition by type."""
    return AGENT_DEFINITIONS.get(agent_type)


def register_agent_definition(definition: AgentDefinition):
    """Register a new agent definition."""
    AGENT_DEFINITIONS[definition.name] = definition


def list_agent_types() -> List[str]:
    """List all available agent types."""
    return list(AGENT_DEFINITIONS.keys())
