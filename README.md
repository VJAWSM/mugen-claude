# Mugen Claude

**Autonomous multi-agent orchestration system for Claude Code**

Mugen Claude is an experimental framework that enables Claude to run autonomously by spawning and coordinating multiple specialized agent processes. The system implements a multi-agent architecture where agents can communicate, collaborate, and coordinate their work to solve complex problems.

## Architecture

```
┌──────────────────────────────────────────────┐
│  Orchestrator (Main Process)                │
│  - Spawns agent processes                   │
│  - Coordinates workflow                     │
│  - Handles user input                       │
└────┬──────────────┬──────────────────────────┘
     │              │
     │              └──> Spawns via multiprocessing
     │
     ↓                   ↓                ↓
┌─────────┐      ┌──────────┐    ┌───────────┐
│Explorer │◄────►│ Planner  │◄──►│ Executor  │
│ Agent   │      │  Agent   │    │   Agent   │
└─────────┘      └──────────┘    └───────────┘
     │                │                │
     └────────────────┴────────────────┘
                      ↓
         ┌────────────────────────────┐
         │  Coordination Layer        │
         │  - Message queues          │
         │  - Shared state (Manager)  │
         │  - File locking            │
         └────────────────────────────┘
```

## Key Features

- **True Multi-Processing**: Agents run as separate OS processes using Python's multiprocessing
- **Agent-to-Agent Communication**: Built-in message passing system for inter-agent coordination
- **File Locking**: OS-level file locking prevents write conflicts between parallel agents
- **Shared State Management**: Centralized coordination manager using multiprocessing.Manager
- **Specialized Agents**: Pre-defined agent types (Explorer, Planner, Executor) with extensibility
- **User Steering**: Interactive mode allows users to guide the orchestration process
- **Autonomous Workflow**: Complete explore → plan → execute workflow with minimal human intervention

## Agent Types

### Built-in Agents

1. **Explorer Agent**: Analyzes codebases, searches for patterns, gathers context
2. **Planner Agent**: Creates implementation plans, breaks down tasks, queries Explorer for info
3. **Executor Agent**: Implements code, modifies files, runs tests with file locking

### Specialized Agents (Extensible)

- Java Agent
- Python Agent
- Frontend Agent (React/Vue/TypeScript)
- Test Agent
- Custom agents can be defined in `config/agents.py`

## Installation

```bash
# Clone the repository
git clone https://github.com/VJAWSM/mugen-claude.git
cd mugen-claude

# Install dependencies
pip install -e .

# Or install from requirements.txt
pip install -r requirements.txt

# Set your Anthropic API key
export ANTHROPIC_API_KEY=your-api-key-here
```

## Usage

### Interactive Mode

```bash
# Run the orchestrator
mugen-claude

# Or directly with Python
python -m mugen_claude.orchestrator
```

### Commands

```
solve <problem>  - Start autonomous problem-solving workflow
status          - Show status of all agent processes
spawn <type>    - Manually spawn an agent (explorer/planner/executor)
quit            - Shutdown orchestrator and all agents
```

### Example Session

```
> solve Implement user authentication system

Phase 1: Exploration
✓ Spawned explorer-1
→ Sent task to explorer-1
✓ Exploration complete

Phase 2: Planning
✓ Spawned planner-1
→ Sent task to planner-1
✓ Planning complete

[Implementation Plan displayed]

Phase 3: Execution
✓ Spawned executor-1
✓ Spawned executor-2
✓ Task T001 completed
✓ Task T002 completed

Workflow Complete!
```

## How It Works

### 1. Problem Solving Workflow

```python
# User submits problem
> solve "Add dark mode to the app"

# Orchestrator spawns Explorer agent
explorer = spawn_agent(ExplorerAgent)

# Explorer analyzes codebase
exploration_result = explorer.explore(
    target=codebase,
    question="Find UI components and theme system"
)

# Orchestrator spawns Planner agent
planner = spawn_agent(PlannerAgent)

# Planner queries Explorer for details
planner.ask_explorer("What CSS framework is used?")
plan = planner.create_plan(problem, exploration_result)

# Orchestrator spawns Executor agents
executors = [spawn_agent(ExecutorAgent) for _ in range(3)]

# Tasks are distributed to executors
for task in plan.tasks:
    executor.execute(task)  # With file locking
```

### 2. Inter-Agent Communication

```python
# Planner sends query to Explorer
planner.send_message(
    to_agent="explorer-1",
    message_type="query",
    content={"question": "What files handle authentication?"}
)

# Explorer receives and responds
explorer.receive_message()
explorer.send_message(
    to_agent="planner-1",
    message_type="response",
    content={"answer": "auth.py and middleware.py"}
)
```

### 3. File Locking

```python
# Executor acquires lock before writing
if coordination.acquire_file_lock(agent_id, "src/auth.py"):
    with open("src/auth.py", "w") as f:
        f.write(new_code)
    coordination.release_file_lock(agent_id, "src/auth.py")
else:
    print("File locked by another agent, waiting...")
```

## Architecture Details

### Coordination Manager

The `CoordinationManager` provides:
- **Message Queues**: Global queue for agent-to-agent messages
- **Shared State**: Dictionary for shared data accessible by all agents
- **File Locks**: Registry of file locks to prevent concurrent writes
- **Agent Status**: Real-time status tracking for all agents

### Agent Process Lifecycle

```python
# 1. Orchestrator spawns process
process = multiprocessing.Process(
    target=agent_wrapper,
    args=(AgentClass, agent_id, coordination_manager)
)
process.start()

# 2. Agent enters run loop
async def run(self):
    while self.running:
        # Check for messages
        msg = self.receive_message()

        if msg.type == "task":
            result = await self.process_task(msg.content)
            self.send_result(result)

# 3. Orchestrator sends shutdown
orchestrator.send_shutdown(agent_id)

# 4. Process terminates
process.join()
```

## Configuration

### Environment Variables

```bash
# Required
ANTHROPIC_API_KEY=your-api-key

# Optional
MUGEN_LOG_LEVEL=INFO
MUGEN_MAX_AGENTS=5
MUGEN_TIMEOUT=120
```

### Agent Definitions

Define custom agents in `mugen_claude/config/agents.py`:

```python
AGENT_DEFINITIONS["rust-agent"] = AgentDefinition(
    name="rust-agent",
    description="Rust development specialist",
    capabilities=["rust", "cargo", "unsafe"],
    tools=["read", "write", "bash"],
    system_prompt_template="You are a Rust expert..."
)
```

## Limitations & Future Work

### Current Limitations

- **No Deep Hierarchies**: Agents cannot spawn sub-agents (multiprocessing limitation)
- **Sequential Planning**: Planner waits for Explorer responses synchronously
- **Limited Error Recovery**: Failed agents don't auto-restart
- **Manual User Approval**: Plan approval is currently manual (can be automated)

### Planned Improvements

- [ ] Distributed execution across multiple machines
- [ ] Agent health monitoring and auto-restart
- [ ] Web UI for real-time agent monitoring
- [ ] Persistent task queues (Redis/RabbitMQ)
- [ ] Dynamic agent creation based on plan requirements
- [ ] Integration with Claude Code's native agent system
- [ ] Support for remote agent processes

## Development

### Project Structure

```
mugen-claude/
├── mugen_claude/
│   ├── __init__.py
│   ├── orchestrator.py      # Main orchestrator
│   ├── coordination/         # Coordination infrastructure
│   │   ├── manager.py       # CoordinationManager
│   │   └── file_lock.py     # File locking
│   ├── agents/              # Agent implementations
│   │   ├── base.py          # BaseAgent class
│   │   ├── explorer.py
│   │   ├── planner.py
│   │   └── executor.py
│   └── config/              # Configuration
│       ├── settings.py
│       └── agents.py        # Agent definitions
├── requirements.txt
├── setup.py
└── README.md
```

### Running Tests

```bash
# Install dev dependencies
pip install -e ".[dev]"

# Run tests (when implemented)
pytest
```

## Contributing

Contributions are welcome! This is an experimental project exploring autonomous agent architectures.

Areas for contribution:
- Additional specialized agents
- Improved coordination algorithms
- Better error handling and recovery
- Performance optimizations
- Documentation improvements

## License

MIT License - see LICENSE file

## Acknowledgments

- Built on top of [Claude Code](https://claude.ai/claude-code) by Anthropic
- Inspired by multi-agent research and autonomous systems
- Uses Python's multiprocessing for true parallel execution

## Contact

Created by VJAWSM - [GitHub](https://github.com/VJAWSM)

---

**Note**: This is an experimental project. The autonomous agent orchestration system is a research prototype and may have rough edges. Use in production environments is not recommended without thorough testing.
