#!/usr/bin/env python3
"""
Test script to verify Claude CLI integration works correctly.
"""
import asyncio
import multiprocessing as mp
import time

from rich.console import Console
from mugen_claude.coordination import CoordinationManager
from mugen_claude.agents import ExplorerAgent

console = Console()


async def test_explorer_agent():
    """Test that Explorer agent can call claude CLI successfully."""
    console.print("\n[bold cyan]Testing Claude CLI Integration[/bold cyan]\n")

    # Create coordination manager
    coord = CoordinationManager()

    # Create explorer agent directly (not as process, for testing)
    agent = ExplorerAgent("test-explorer", "explorer", coord)

    try:
        # Test a simple query
        console.print("[yellow]Sending test query to Claude CLI...[/yellow]")
        response = await agent.query_claude(
            "What is 5 + 7? Just give me the number."
        )

        console.print(f"[green]✓ Response received:[/green] {response}")

        # Test conversation history
        console.print("\n[yellow]Testing conversation history...[/yellow]")
        followup = await agent.query_claude(
            "What was the question I just asked?"
        )

        console.print(f"[green]✓ Followup response:[/green] {followup[:200]}")

        console.print("\n[bold green]✓ Claude CLI integration working![/bold green]")

        return True

    except Exception as e:
        console.print(f"\n[bold red]✗ Error:[/bold red] {e}")
        import traceback
        traceback.print_exc()
        return False
    finally:
        coord.shutdown()


if __name__ == "__main__":
    mp.set_start_method('fork', force=True)
    success = asyncio.run(test_explorer_agent())
    exit(0 if success else 1)
