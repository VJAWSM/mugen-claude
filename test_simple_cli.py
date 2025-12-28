#!/usr/bin/env python3
"""
Simplest possible test - just call Claude CLI directly.
"""
import asyncio
import sys

async def test_async_subprocess():
    """Test async subprocess call to claude CLI."""
    print("Testing async subprocess call to Claude CLI...", flush=True)

    cmd = [
        'claude',
        '--print',
        '--output-format', 'json',
        '--system-prompt', 'You are a helpful assistant.',
        '--tools', 'Read',
        '--no-session-persistence',
        '--model', 'sonnet',
        'What is 10 + 5? Just give me the number.'
    ]

    print(f"Command: {' '.join(cmd[:5])}...", flush=True)

    try:
        print("Creating subprocess...", flush=True)
        process = await asyncio.create_subprocess_exec(
            *cmd,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE
        )

        print("Waiting for subprocess...", flush=True)
        stdout, stderr = await asyncio.wait_for(
            process.communicate(),
            timeout=30.0
        )

        print(f"Process completed with return code: {process.returncode}", flush=True)

        stdout_text = stdout.decode('utf-8')
        stderr_text = stderr.decode('utf-8')

        if stderr_text:
            print(f"STDERR: {stderr_text}", flush=True)

        print(f"STDOUT length: {len(stdout_text)} bytes", flush=True)

        import json
        data = json.loads(stdout_text)
        print(f"Result: {data.get('result')}", flush=True)
        print(f"Cost: ${data.get('total_cost_usd', 0):.4f}", flush=True)

        print("✓ Test successful!", flush=True)
        return True

    except asyncio.TimeoutError:
        print("✗ Timeout after 30 seconds", flush=True)
        return False
    except Exception as e:
        print(f"✗ Error: {e}", flush=True)
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = asyncio.run(test_async_subprocess())
    sys.exit(0 if success else 1)
