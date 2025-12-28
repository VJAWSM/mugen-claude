#!/usr/bin/env python3
"""
Debug agent execution with explicit output.
"""
import asyncio
import sys

from mugen_claude.coordination import CoordinationManager
from mugen_claude.agents import ExplorerAgent


async def test_explorer_directly():
    """Test explorer agent directly in the main process."""
    print("=== Testing Explorer Agent Directly ===\n", flush=True)

    # Create coordination manager
    coord = CoordinationManager()

    # Create explorer agent (in SAME process for debugging)
    agent = ExplorerAgent("explorer-debug", "explorer", coord)

    print("Agent created", flush=True)

    # Create a simple task
    task = {
        'task': 'explore',
        'target': './mugen_claude',
        'question': 'What Python files are in this directory?',
        'scope': 'mugen_claude'
    }

    print(f"Calling process_task with task: {task}", flush=True)

    try:
        result = await agent.process_task(task)
        print(f"\n✓ Result received:", flush=True)
        print(f"  Question: {result.get('question')}", flush=True)
        print(f"  Target: {result.get('target')}", flush=True)
        print(f"  Analysis length: {len(result.get('analysis', ''))} chars", flush=True)
        return True

    except Exception as e:
        print(f"\n✗ Error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return False

    finally:
        coord.shutdown()


if __name__ == "__main__":
    success = asyncio.run(test_explorer_directly())
    sys.exit(0 if success else 1)
