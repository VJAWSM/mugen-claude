#!/usr/bin/env python3
"""
End-to-end test of the full orchestrator workflow.

Tests the complete explore → plan → execute workflow with a codebase analysis problem.
"""
import asyncio
import multiprocessing as mp
import sys
import os

from rich.console import Console
from mugen_claude.orchestrator import Orchestrator

console = Console()


async def main():
    """Run end-to-end test with codebase analysis problem."""

    console.print("[bold cyan]═══════════════════════════════════════════════════════[/bold cyan]")
    console.print("[bold cyan]  End-to-End Orchestrator Workflow Test               [/bold cyan]")
    console.print("[bold cyan]═══════════════════════════════════════════════════════[/bold cyan]\n")

    # Create orchestrator
    orchestrator = Orchestrator()

    # Problem that fits current agent capabilities (code analysis)
    problem = """Analyze the mugen_claude codebase structure and create a comprehensive documentation report. The report should explain:
1. The overall architecture and how the multiprocessing system works
2. The role of each agent type (Explorer, Planner, Executor)
3. How the coordination infrastructure works (CoordinationManager, message queues, file locking)
4. The workflow from problem input to solution output

Create a markdown report file named 'ARCHITECTURE_ANALYSIS.md' with this information."""

    console.print(f"[bold]Test Problem:[/bold]\n{problem}\n")
    console.print("[yellow]Starting workflow...[/yellow]\n")

    try:
        # Run the complete workflow
        await orchestrator.execute_problem(
            problem=problem,
            working_dir=os.getcwd()
        )

        console.print("\n[bold green]✓ Workflow completed successfully![/bold green]")

        # Check for created files
        console.print("\n[yellow]Checking for created report...[/yellow]")
        report_file = "ARCHITECTURE_ANALYSIS.md"

        if os.path.exists(report_file):
            size = os.path.getsize(report_file)
            console.print(f"[green]✓ Report created: {report_file} ({size} bytes)[/green]")

            # Show first few lines
            console.print(f"\n[yellow]Preview:[/yellow]")
            with open(report_file, 'r') as f:
                lines = f.readlines()[:25]
                for line in lines:
                    console.print(f"  {line.rstrip()}")
                if len(lines) == 25:
                    console.print("  ...")
        else:
            # Check for any created markdown files
            import glob
            md_files = [f for f in glob.glob("*.md") if f not in ['README.md', 'DEMO_RESULTS.md', 'REFACTOR_SUMMARY.md', 'LICENSE']]
            if md_files:
                console.print(f"[yellow]⚠ {report_file} not found, but found other files:[/yellow]")
                for f in md_files:
                    console.print(f"  - {f}")
            else:
                console.print(f"[yellow]⚠ {report_file} not created[/yellow]")

        # Show agent status
        console.print("\n[yellow]Final agent status:[/yellow]")
        try:
            table = orchestrator.get_agent_status_table()
            console.print(table)
        except Exception as e:
            console.print(f"[yellow]Could not get agent status table: {e}[/yellow]")

        return True

    except Exception as e:
        console.print(f"\n[bold red]✗ Workflow failed:[/bold red] {e}")
        import traceback
        traceback.print_exc()
        return False

    finally:
        # Shutdown orchestrator
        console.print("\n[yellow]Shutting down orchestrator...[/yellow]")
        try:
            orchestrator.shutdown()
        except Exception as e:
            console.print(f"[yellow]Shutdown error (expected): {e}[/yellow]")


if __name__ == "__main__":
    # Required for multiprocessing on macOS
    mp.set_start_method('fork', force=True)

    success = asyncio.run(main())
    exit(0 if success else 1)
