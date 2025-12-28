"""
Main Orchestrator - Spawns and coordinates multiple agent processes.
"""
import asyncio
import multiprocessing as mp
import os
import sys
from typing import Dict, List, Optional
from datetime import datetime
import json

from rich.console import Console
from rich.table import Table
from rich.live import Live
from rich.panel import Panel
from rich.layout import Layout

from .coordination import CoordinationManager, AgentMessage
from .agents import ExplorerAgent, PlannerAgent, ExecutorAgent


console = Console()


def agent_process_wrapper(agent_class, agent_id, agent_type, coordination_manager, api_key):
    """
    Wrapper function to run an agent in a separate process.
    This is needed because multiprocessing requires a top-level function.
    """
    try:
        agent = agent_class(agent_id, agent_type, coordination_manager, api_key)
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        print(f"[{agent_id}] Interrupted")
    except Exception as e:
        print(f"[{agent_id}] Error: {e}")
        import traceback
        traceback.print_exc()


class Orchestrator:
    """
    Main orchestrator that spawns and coordinates agent processes.
    Handles user input and manages the overall workflow.
    """

    def __init__(self, api_key: Optional[str] = None):
        """Initialize the orchestrator."""
        self.api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")

        self.coordination = CoordinationManager()
        self.processes: Dict[str, mp.Process] = {}
        self.agent_counter = 0
        self.running = False

    def spawn_agent(self, agent_class, agent_type: str) -> str:
        """
        Spawn a new agent process.

        Args:
            agent_class: The agent class to instantiate
            agent_type: Type of agent (explorer, planner, executor)

        Returns:
            Agent ID
        """
        self.agent_counter += 1
        agent_id = f"{agent_type}-{self.agent_counter}"

        process = mp.Process(
            target=agent_process_wrapper,
            args=(agent_class, agent_id, agent_type, self.coordination, self.api_key)
        )
        process.start()

        self.processes[agent_id] = process
        console.print(f"[green]✓[/green] Spawned {agent_type} agent: {agent_id}")

        return agent_id

    def send_task_to_agent(self, agent_id: str, task: Dict):
        """Send a task to a specific agent."""
        msg = AgentMessage(
            from_agent="orchestrator",
            to_agent=agent_id,
            message_type="task",
            content=task
        )
        self.coordination.send_message(msg)
        console.print(f"[blue]→[/blue] Sent task to {agent_id}")

    async def wait_for_result(self, agent_id: str, timeout: float = 120) -> Optional[Dict]:
        """Wait for a result from an agent."""
        start_time = asyncio.get_event_loop().time()

        while asyncio.get_event_loop().time() - start_time < timeout:
            # Check for result message
            msg = self.coordination.get_message("orchestrator", timeout=0.5)

            if msg and msg.from_agent == agent_id and msg.message_type == 'result':
                return msg.content.get('result')

            await asyncio.sleep(0.5)

        console.print(f"[red]✗[/red] Timeout waiting for result from {agent_id}")
        return None

    def get_agent_status_table(self) -> Table:
        """Generate a status table for all agents."""
        table = Table(title="Agent Status")
        table.add_column("Agent ID", style="cyan")
        table.add_column("Type", style="magenta")
        table.add_column("Status", style="green")
        table.add_column("Current Task", style="yellow")

        statuses = self.coordination.get_all_agent_status()
        for agent_id, status in statuses.items():
            table.add_row(
                agent_id,
                status['agent_type'],
                status['status'],
                status.get('current_task', '-')[:50]
            )

        return table

    async def execute_problem(self, problem: str, working_dir: str = "."):
        """
        Execute a complete problem-solving workflow.

        Args:
            problem: The problem description
            working_dir: Working directory for the implementation
        """
        console.print(Panel(f"[bold]Problem:[/bold]\n{problem}", title="Starting Workflow"))

        # Spawn Explorer and Planner agents
        explorer_id = self.spawn_agent(ExplorerAgent, "explorer")
        planner_id = self.spawn_agent(PlannerAgent, "planner")

        await asyncio.sleep(2)  # Give agents time to start

        # Step 1: Exploration
        console.print("\n[bold cyan]Phase 1: Exploration[/bold cyan]")
        exploration_task = {
            'task': 'explore',
            'target': working_dir,
            'question': f"Explore the codebase to gather context for: {problem}",
            'scope': ''
        }
        self.send_task_to_agent(explorer_id, exploration_task)

        exploration_result = await self.wait_for_result(explorer_id, timeout=60)
        if not exploration_result:
            console.print("[red]Exploration failed[/red]")
            return

        console.print("[green]✓[/green] Exploration complete")

        # Step 2: Planning
        console.print("\n[bold cyan]Phase 2: Planning[/bold cyan]")
        planning_task = {
            'task': 'plan',
            'problem': problem,
            'context': json.dumps(exploration_result),
            'explorer_id': explorer_id
        }
        self.send_task_to_agent(planner_id, planning_task)

        planning_result = await self.wait_for_result(planner_id, timeout=120)
        if not planning_result:
            console.print("[red]Planning failed[/red]")
            return

        console.print("[green]✓[/green] Planning complete")

        # Display the plan
        console.print(Panel(planning_result.get('plan', 'No plan generated'), title="Implementation Plan"))

        # Check if new agent types are required
        required_agents = planning_result.get('requires_new_agents', [])
        if required_agents:
            console.print(f"\n[yellow]Note:[/yellow] Plan requires specialized agents: {', '.join(required_agents)}")
            console.print("[yellow]For this prototype, we'll use generic executor agents.[/yellow]")

        # Step 3: User approval
        console.print("\n[bold]Review the plan above. Proceed with implementation? (y/n)[/bold]")
        # In a real implementation, this would wait for user input
        # For now, we'll auto-proceed
        proceed = True

        if not proceed:
            console.print("[yellow]Implementation cancelled by user[/yellow]")
            return

        # Step 4: Execution
        console.print("\n[bold cyan]Phase 3: Execution[/bold cyan]")

        tasks = planning_result.get('structured_tasks', [])
        if not tasks:
            console.print("[yellow]No structured tasks found in plan. Skipping execution.[/yellow]")
            return

        # Spawn executor agents (one per task for now)
        executor_ids = []
        for i in range(min(len(tasks), 3)):  # Limit to 3 concurrent executors
            executor_id = self.spawn_agent(ExecutorAgent, "executor")
            executor_ids.append(executor_id)

        await asyncio.sleep(2)  # Give executors time to start

        # Assign tasks to executors
        for i, task in enumerate(tasks[:3]):  # Execute first 3 tasks
            executor_id = executor_ids[i % len(executor_ids)]

            execution_task = {
                'task': 'implement',
                'task_id': task.get('task_id', f'T{i+1}'),
                'description': task.get('description', ''),
                'files': task.get('files', []),
                'specifications': task.get('description', ''),
                'acceptance_criteria': task.get('acceptance_criteria', []),
                'working_directory': working_dir
            }

            self.send_task_to_agent(executor_id, execution_task)

        # Wait for all execution results
        console.print(f"\n[bold]Waiting for {len(tasks[:3])} tasks to complete...[/bold]")
        execution_results = []

        for executor_id in executor_ids:
            result = await self.wait_for_result(executor_id, timeout=180)
            if result:
                execution_results.append(result)
                success = result.get('success', False)
                status = "[green]✓[/green]" if success else "[red]✗[/red]"
                console.print(f"{status} Task {result.get('task_id')} completed")

        # Summary
        console.print("\n" + "="*60)
        console.print("[bold green]Workflow Complete![/bold green]")
        console.print(f"Exploration: ✓")
        console.print(f"Planning: ✓")
        console.print(f"Execution: {len(execution_results)}/{len(tasks[:3])} tasks completed")

    async def interactive_mode(self):
        """Run in interactive mode where user can send commands."""
        self.running = True
        console.print("[bold cyan]Mugen Claude Orchestrator[/bold cyan]")
        console.print("Multi-agent autonomous orchestration system\n")

        console.print("Commands:")
        console.print("  solve <problem>  - Start problem-solving workflow")
        console.print("  status          - Show agent status")
        console.print("  spawn <type>    - Spawn a new agent (explorer/planner/executor)")
        console.print("  quit            - Shut down orchestrator\n")

        while self.running:
            try:
                # In a real implementation, we'd use asyncio queue for non-blocking input
                # For prototype, we'll use simple input
                user_input = await asyncio.get_event_loop().run_in_executor(
                    None, input, "[bold]> [/bold]"
                )

                if not user_input.strip():
                    continue

                parts = user_input.strip().split(maxsplit=1)
                command = parts[0].lower()

                if command == "quit":
                    console.print("[yellow]Shutting down...[/yellow]")
                    self.running = False

                elif command == "status":
                    table = self.get_agent_status_table()
                    console.print(table)

                elif command == "spawn" and len(parts) > 1:
                    agent_type = parts[1].lower()
                    agent_map = {
                        'explorer': ExplorerAgent,
                        'planner': PlannerAgent,
                        'executor': ExecutorAgent
                    }
                    if agent_type in agent_map:
                        self.spawn_agent(agent_map[agent_type], agent_type)
                    else:
                        console.print(f"[red]Unknown agent type: {agent_type}[/red]")

                elif command == "solve" and len(parts) > 1:
                    problem = parts[1]
                    await self.execute_problem(problem, os.getcwd())

                else:
                    console.print("[red]Unknown command[/red]")

            except KeyboardInterrupt:
                console.print("\n[yellow]Interrupted. Type 'quit' to exit.[/yellow]")
            except Exception as e:
                console.print(f"[red]Error: {e}[/red]")

        self.shutdown()

    def shutdown(self):
        """Shutdown all agent processes."""
        console.print("\n[yellow]Shutting down agents...[/yellow]")

        # Send shutdown message to all agents
        for agent_id in list(self.processes.keys()):
            msg = AgentMessage(
                from_agent="orchestrator",
                to_agent=agent_id,
                message_type="shutdown",
                content={}
            )
            self.coordination.send_message(msg)

        # Wait for processes to finish
        for agent_id, process in self.processes.items():
            process.join(timeout=5)
            if process.is_alive():
                console.print(f"[red]Force terminating {agent_id}[/red]")
                process.terminate()
                process.join()

        self.coordination.shutdown()
        console.print("[green]✓[/green] Shutdown complete")


def main():
    """Main entry point."""
    # Check for API key
    if not os.getenv("ANTHROPIC_API_KEY"):
        console.print("[red]Error: ANTHROPIC_API_KEY environment variable not set[/red]")
        console.print("Please set it before running:")
        console.print("  export ANTHROPIC_API_KEY=your-api-key")
        sys.exit(1)

    orchestrator = Orchestrator()

    try:
        asyncio.run(orchestrator.interactive_mode())
    except KeyboardInterrupt:
        console.print("\n[yellow]Interrupted[/yellow]")
        orchestrator.shutdown()


if __name__ == "__main__":
    main()
