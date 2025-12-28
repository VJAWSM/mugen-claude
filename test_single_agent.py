#!/usr/bin/env python3
"""
Test a single agent in isolation to debug issues.
"""
import asyncio
import multiprocessing as mp
import time

from rich.console import Console
from mugen_claude.coordination import CoordinationManager, AgentMessage
from mugen_claude.agents import ExplorerAgent

console = Console()


def run_explorer_agent(coordination):
    """Run explorer agent in separate process."""
    console.print("[cyan]Explorer process started[/cyan]")
    agent = ExplorerAgent("explorer-test", "explorer", coordination)

    try:
        asyncio.run(agent.run())
    except KeyboardInterrupt:
        console.print("[yellow]Explorer interrupted[/yellow]")
    except Exception as e:
        console.print(f"[red]Explorer error: {e}[/red]")
        import traceback
        traceback.print_exc()


async def main():
    """Test explorer agent in isolation."""
    console.print("[bold cyan]Testing Single Explorer Agent[/bold cyan]\n")

    # Create coordination manager
    coord = CoordinationManager()

    # Spawn explorer process
    console.print("[yellow]Spawning explorer process...[/yellow]")
    process = mp.Process(target=run_explorer_agent, args=(coord,))
    process.start()

    # Wait for agent to start
    await asyncio.sleep(2)

    # Send a simple task
    console.print("[yellow]Sending test task...[/yellow]")
    task = {
        'task': 'explore',
        'target': '.',
        'question': 'List the Python files in the mugen_claude directory',
        'scope': 'mugen_claude'
    }

    msg = AgentMessage(
        from_agent="test-orchestrator",
        to_agent="explorer-test",
        message_type="task",
        content=task
    )
    coord.send_message(msg)

    # Wait for result
    console.print("[yellow]Waiting for result (60s timeout)...[/yellow]")
    start_time = time.time()
    result_received = False

    while time.time() - start_time < 60:
        msg = coord.get_message("test-orchestrator", timeout=1.0)
        if msg:
            console.print(f"[green]✓ Received message type: {msg.message_type}[/green]")
            if msg.message_type == 'result':
                console.print(f"[green]✓ Result content:[/green]")
                console.print(msg.content)
                result_received = True
                break
            elif msg.message_type == 'error':
                console.print(f"[red]✗ Error from agent:[/red]")
                console.print(msg.content)
                break

        await asyncio.sleep(0.5)

    if not result_received:
        console.print("[red]✗ Timeout - no result received[/red]")

    # Check agent status
    console.print("\n[yellow]Agent status:[/yellow]")
    statuses = coord.get_all_agent_status()
    for agent_id, status in statuses.items():
        console.print(f"  {agent_id}: {status}")

    # Shutdown
    console.print("\n[yellow]Shutting down...[/yellow]")
    shutdown_msg = AgentMessage(
        from_agent="test-orchestrator",
        to_agent="explorer-test",
        message_type="shutdown",
        content={}
    )
    coord.send_message(shutdown_msg)

    process.join(timeout=5)
    if process.is_alive():
        console.print("[red]Force terminating process[/red]")
        process.terminate()
        process.join()

    coord.shutdown()
    console.print("[green]✓ Test complete[/green]")


if __name__ == "__main__":
    mp.set_start_method('fork', force=True)
    asyncio.run(main())
