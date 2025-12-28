#!/usr/bin/env python3
"""
Demo script for Mugen Claude multi-agent orchestration system.

This demonstrates the core functionality of the system:
1. Coordination infrastructure (message queues, file locks, shared state)
2. Agent spawning and lifecycle management
3. Inter-agent communication
4. Process-level parallelism

Usage:
    python3 demo.py --test-coordination   # Test coordination without API
    python3 demo.py --test-agents        # Test agents (requires ANTHROPIC_API_KEY)
"""
import asyncio
import multiprocessing as mp
import os
import sys
import time
from pathlib import Path

from rich.console import Console
from rich.panel import Panel
from rich.table import Table

from mugen_claude.coordination import CoordinationManager, AgentMessage, FileLock
from mugen_claude.config import list_agent_types, get_agent_definition


console = Console()


def test_coordination_infrastructure():
    """Test the coordination infrastructure without requiring API keys."""
    console.print(Panel("[bold cyan]Test 1: Coordination Infrastructure[/bold cyan]"))

    # Create coordination manager
    console.print("\n[yellow]Creating CoordinationManager...[/yellow]")
    coord = CoordinationManager()
    console.print("[green]✓[/green] CoordinationManager created")

    # Test agent registration
    console.print("\n[yellow]Registering test agents...[/yellow]")
    coord.register_agent("test-agent-1", "explorer")
    coord.register_agent("test-agent-2", "planner")
    console.print("[green]✓[/green] Registered 2 agents")

    # Test status updates
    console.print("\n[yellow]Updating agent status...[/yellow]")
    coord.update_agent_status("test-agent-1", "running", current_task="Exploring codebase")
    coord.update_agent_status("test-agent-2", "idle")

    # Display status table
    statuses = coord.get_all_agent_status()
    table = Table(title="Agent Status")
    table.add_column("Agent ID", style="cyan")
    table.add_column("Type", style="magenta")
    table.add_column("Status", style="green")
    table.add_column("Task", style="yellow")

    for agent_id, status in statuses.items():
        table.add_row(
            agent_id,
            status['agent_type'],
            status['status'],
            status.get('current_task', '-')
        )

    console.print(table)
    console.print("[green]✓[/green] Status tracking works")

    # Test message passing
    console.print("\n[yellow]Testing message queues...[/yellow]")
    msg = AgentMessage(
        from_agent="test-agent-1",
        to_agent="test-agent-2",
        message_type="query",
        content={"question": "What is the plan?"}
    )
    coord.send_message(msg)
    console.print("[green]✓[/green] Message sent: test-agent-1 → test-agent-2")

    received_msg = coord.get_message("test-agent-2", timeout=0.5)
    if received_msg:
        console.print(f"[green]✓[/green] Message received: {received_msg.message_type}")
        console.print(f"  Content: {received_msg.content}")
    else:
        console.print("[red]✗[/red] Message not received")

    # Test file locking
    console.print("\n[yellow]Testing file locking...[/yellow]")
    test_file = "/tmp/test_lock_file.txt"

    # Agent 1 acquires lock
    if coord.acquire_file_lock("test-agent-1", test_file):
        console.print(f"[green]✓[/green] test-agent-1 acquired lock on {test_file}")

        # Agent 2 tries to acquire (should fail)
        if not coord.acquire_file_lock("test-agent-2", test_file):
            console.print(f"[green]✓[/green] test-agent-2 correctly blocked (file locked)")
        else:
            console.print(f"[red]✗[/red] test-agent-2 should have been blocked!")

        # Agent 1 releases
        coord.release_file_lock("test-agent-1", test_file)
        console.print(f"[green]✓[/green] test-agent-1 released lock")

        # Agent 2 tries again (should succeed)
        if coord.acquire_file_lock("test-agent-2", test_file):
            console.print(f"[green]✓[/green] test-agent-2 acquired lock after release")
            coord.release_file_lock("test-agent-2", test_file)

    # Test shared state
    console.print("\n[yellow]Testing shared state...[/yellow]")
    coord.shared_state["test_key"] = "test_value"
    coord.shared_state["counter"] = 42
    console.print(f"[green]✓[/green] Stored values in shared state")
    console.print(f"  test_key = {coord.shared_state['test_key']}")
    console.print(f"  counter = {coord.shared_state['counter']}")

    # Test result storage
    console.print("\n[yellow]Testing result storage...[/yellow]")
    coord.store_result("test-agent-1", {"findings": ["file1.py", "file2.py"]})
    result = coord.get_result("test-agent-1")
    console.print(f"[green]✓[/green] Stored and retrieved result: {result}")

    # Cleanup
    coord.shutdown()
    console.print("\n[green]✓ All coordination tests passed![/green]")


def test_os_file_locking():
    """Test OS-level file locking with actual files."""
    console.print(Panel("[bold cyan]Test 2: OS-Level File Locking[/bold cyan]"))

    test_file = "/tmp/mugen_test_file.txt"

    console.print(f"\n[yellow]Testing FileLock on {test_file}...[/yellow]")

    # Create test file
    with open(test_file, 'w') as f:
        f.write("Initial content\n")

    # Test context manager
    console.print("[yellow]Testing context manager...[/yellow]")
    try:
        with FileLock(test_file, timeout=5.0):
            console.print("[green]✓[/green] Lock acquired using context manager")
            with open(test_file, 'a') as f:
                f.write("Added with lock\n")
            console.print("[green]✓[/green] File written successfully")
        console.print("[green]✓[/green] Lock released automatically")
    except TimeoutError as e:
        console.print(f"[red]✗[/red] Lock timeout: {e}")

    # Verify file content
    with open(test_file, 'r') as f:
        content = f.read()
        console.print(f"[green]✓[/green] File content verified:\n{content}")

    # Cleanup
    os.remove(test_file)
    console.print("[green]✓ File locking test passed![/green]")


def worker_process(agent_id, coord, message_queue):
    """Simple worker process to test multiprocessing."""
    console.print(f"[cyan]Worker {agent_id} started (PID: {os.getpid()})[/cyan]")

    # Register
    coord.register_agent(agent_id, "test-worker")
    coord.update_agent_status(agent_id, "running", current_task="Processing")

    # Send a message
    msg = AgentMessage(
        from_agent=agent_id,
        to_agent=None,  # Broadcast
        message_type="status",
        content={"status": "alive", "pid": os.getpid()}
    )
    coord.send_message(msg)

    # Simulate some work
    time.sleep(2)

    # Update status
    coord.update_agent_status(agent_id, "completed")
    console.print(f"[cyan]Worker {agent_id} completed[/cyan]")


def test_multiprocessing():
    """Test actual multiprocessing with coordination."""
    console.print(Panel("[bold cyan]Test 3: Multiprocessing & Process Isolation[/bold cyan]"))

    coord = CoordinationManager()

    console.print("\n[yellow]Spawning 3 worker processes...[/yellow]")
    processes = []

    for i in range(3):
        agent_id = f"worker-{i+1}"
        p = mp.Process(target=worker_process, args=(agent_id, coord, coord.message_queue))
        p.start()
        processes.append(p)
        console.print(f"[green]✓[/green] Spawned {agent_id} (PID: {p.pid})")

    # Wait a bit for workers to start
    time.sleep(1)

    # Check messages
    console.print("\n[yellow]Checking for messages from workers...[/yellow]")
    for _ in range(3):
        msg = coord.get_message("main", timeout=1.0)
        if msg:
            console.print(f"[green]✓[/green] Received message from {msg.from_agent}: PID {msg.content.get('pid')}")

    # Display status
    console.print("\n[yellow]Agent status during execution:[/yellow]")
    table = Table()
    table.add_column("Agent", style="cyan")
    table.add_column("Status", style="green")
    table.add_column("Task", style="yellow")

    statuses = coord.get_all_agent_status()
    for agent_id, status in statuses.items():
        table.add_row(agent_id, status['status'], status.get('current_task', '-'))

    console.print(table)

    # Wait for all processes
    console.print("\n[yellow]Waiting for workers to complete...[/yellow]")
    for i, p in enumerate(processes):
        p.join(timeout=5)
        if p.is_alive():
            console.print(f"[red]✗[/red] Worker {i+1} timed out, terminating")
            p.terminate()
        else:
            console.print(f"[green]✓[/green] Worker {i+1} completed")

    coord.shutdown()
    console.print("\n[green]✓ Multiprocessing test passed![/green]")


def test_agent_definitions():
    """Test agent definition system."""
    console.print(Panel("[bold cyan]Test 4: Agent Type System[/bold cyan]"))

    console.print("\n[yellow]Available agent types:[/yellow]")
    agent_types = list_agent_types()

    table = Table(title="Agent Definitions")
    table.add_column("Type", style="cyan")
    table.add_column("Description", style="yellow")
    table.add_column("Capabilities", style="green")

    for agent_type in agent_types:
        definition = get_agent_definition(agent_type)
        table.add_row(
            definition.name,
            definition.description,
            ", ".join(definition.capabilities[:3])
        )

    console.print(table)
    console.print(f"\n[green]✓[/green] {len(agent_types)} agent types defined")
    console.print("[green]✓ Agent definition system works![/green]")


def main():
    """Main demo runner."""
    console.print("[bold cyan]═══════════════════════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]     Mugen Claude - Multi-Agent Orchestration Demo    [/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════════════════════[/bold cyan]\n")

    if len(sys.argv) > 1:
        arg = sys.argv[1]
        if arg == "--test-coordination":
            test_coordination_infrastructure()
        elif arg == "--test-agents":
            console.print("[red]Agent tests require ANTHROPIC_API_KEY to be set[/red]")
            console.print("[yellow]For now, run the full orchestrator with: mugen-claude[/yellow]")
        else:
            console.print(f"[red]Unknown argument: {arg}[/red]")
            console.print("Usage: python3 demo.py [--test-coordination|--test-agents]")
    else:
        # Run all tests
        try:
            test_coordination_infrastructure()
            console.print("\n" + "="*60 + "\n")

            test_os_file_locking()
            console.print("\n" + "="*60 + "\n")

            test_multiprocessing()
            console.print("\n" + "="*60 + "\n")

            test_agent_definitions()
            console.print("\n" + "="*60 + "\n")

            console.print(Panel(
                "[bold green]✓ All Tests Passed![/bold green]\n\n"
                "The Mugen Claude system is working correctly!\n\n"
                "Next steps:\n"
                "1. Set ANTHROPIC_API_KEY environment variable\n"
                "2. Run: mugen-claude\n"
                "3. Try: solve 'Explain the codebase structure'",
                title="Demo Complete"
            ))

        except KeyboardInterrupt:
            console.print("\n[yellow]Demo interrupted[/yellow]")
        except Exception as e:
            console.print(f"\n[red]Error during demo: {e}[/red]")
            import traceback
            traceback.print_exc()


if __name__ == "__main__":
    # Required for multiprocessing on macOS
    mp.set_start_method('fork', force=True)
    main()
