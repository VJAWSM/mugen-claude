"""
Base agent class for all agent processes.
"""
import asyncio
import json
import subprocess
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List
from datetime import datetime

from ..coordination import CoordinationManager, AgentMessage


class BaseAgent(ABC):
    """
    Base class for all agent processes.
    Each agent runs in its own process and communicates via the coordination manager.
    Uses the `claude` CLI command for Claude API interaction.
    """

    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        coordination_manager: CoordinationManager,
    ):
        """
        Initialize the base agent.

        Args:
            agent_id: Unique identifier for this agent instance
            agent_type: Type of agent (explorer, planner, executor, etc.)
            coordination_manager: Shared coordination manager
        """
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.coordination = coordination_manager
        self.running = False

        # Conversation history for this agent
        self.conversation_history = []

        # Register with coordination manager
        self.coordination.register_agent(self.agent_id, self.agent_type)

    @abstractmethod
    def get_system_prompt(self) -> str:
        """
        Get the system prompt for this agent type.
        Each agent type should define its own specialized prompt.
        """
        pass

    @abstractmethod
    def get_allowed_tools(self) -> str:
        """
        Get comma-separated list of tools this agent can use.
        Examples: "Read,Glob,Grep" or "Read,Write,Edit,Bash"
        """
        pass

    @abstractmethod
    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a task assigned to this agent.
        Each agent type implements its own task processing logic.

        Args:
            task: Task dictionary with task details

        Returns:
            Result dictionary
        """
        pass

    def _format_conversation(self) -> str:
        """
        Format conversation history as a single prompt string.

        Returns:
            Formatted conversation string
        """
        if not self.conversation_history:
            return ""

        # Format previous conversation
        parts = []
        for msg in self.conversation_history[:-1]:  # All but the last message
            role = msg['role'].title()
            content = msg['content']
            parts.append(f"{role}: {content}")

        # Add current message
        if self.conversation_history:
            current = self.conversation_history[-1]
            if parts:
                conversation_context = "\n\n".join(parts)
                prompt = f"Previous conversation:\n{conversation_context}\n\nCurrent question:\n{current['content']}"
            else:
                prompt = current['content']
        else:
            prompt = ""

        return prompt

    async def query_claude(self, user_message: str, max_tokens: int = 4096) -> str:
        """
        Send a query to Claude via CLI and get a response.

        Args:
            user_message: The user message to send
            max_tokens: Maximum tokens in response (not used with CLI, for compatibility)

        Returns:
            Claude's response text
        """
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        # Format conversation as prompt
        prompt = self._format_conversation()

        # Build claude CLI command
        cmd = [
            'claude',
            '--print',
            '--output-format', 'json',
            '--system-prompt', self.get_system_prompt(),
            '--tools', self.get_allowed_tools(),
            '--no-session-persistence',
            '--model', 'sonnet',
            prompt
        ]

        # Execute claude command (async subprocess)
        try:
            print(f"[{self.agent_id}] Calling Claude CLI...")

            # Run subprocess asynchronously
            process = await asyncio.create_subprocess_exec(
                *cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Wait for completion with timeout
            try:
                stdout, stderr = await asyncio.wait_for(
                    process.communicate(),
                    timeout=120.0
                )
            except asyncio.TimeoutError:
                process.kill()
                raise Exception("Claude command timed out after 120 seconds")

            stdout_text = stdout.decode('utf-8')
            stderr_text = stderr.decode('utf-8')

            if process.returncode != 0:
                print(f"[{self.agent_id}] Claude CLI error: {stderr_text}")
                raise Exception(f"Claude CLI exited with code {process.returncode}: {stderr_text}")

            # Parse JSON response
            response_data = json.loads(stdout_text)

            # Check for errors
            if response_data.get('is_error'):
                error_msg = response_data.get('result', 'Unknown error')
                raise Exception(f"Claude error: {error_msg}")

            # Extract response text
            response_text = response_data.get('result', '')

            # Log usage (optional)
            cost = response_data.get('total_cost_usd', 0)
            duration = response_data.get('duration_ms', 0)
            print(f"[{self.agent_id}] Query completed - Cost: ${cost:.4f}, Duration: {duration}ms")

        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse Claude response: {e}\nOutput: {stdout_text[:500]}")
        except Exception as e:
            raise Exception(f"Error calling Claude CLI: {e}")

        # Add assistant response to history
        self.conversation_history.append({
            "role": "assistant",
            "content": response_text
        })

        return response_text

    def send_message(self, to_agent: Optional[str], message_type: str, content: Dict[str, Any]):
        """
        Send a message to another agent or broadcast.

        Args:
            to_agent: Target agent ID (None for broadcast)
            message_type: Type of message
            content: Message content
        """
        msg = AgentMessage(
            from_agent=self.agent_id,
            to_agent=to_agent,
            message_type=message_type,
            content=content
        )
        self.coordination.send_message(msg)

    def receive_message(self, timeout: float = 0.1) -> Optional[AgentMessage]:
        """
        Receive a message from the message queue.

        Args:
            timeout: Timeout in seconds

        Returns:
            AgentMessage if available, None otherwise
        """
        return self.coordination.get_message(self.agent_id, timeout)

    def update_status(self, status: str, current_task: Optional[str] = None, error: Optional[str] = None):
        """Update this agent's status in the coordination manager."""
        self.coordination.update_agent_status(
            self.agent_id,
            status,
            current_task,
            error
        )

    async def run(self):
        """
        Main run loop for the agent.
        Listens for messages and processes tasks.
        """
        self.running = True
        self.update_status('idle')

        print(f"[{self.agent_id}] Agent started (type: {self.agent_type})")

        while self.running:
            # Check for messages
            msg = self.receive_message(timeout=0.5)

            if msg:
                if msg.message_type == 'task':
                    # Process task
                    self.update_status('running', str(msg.content.get('task', 'Unknown task')))
                    print(f"[{self.agent_id}] Received task: {msg.content.get('task')}")

                    try:
                        result = await self.process_task(msg.content)

                        # Send result back
                        self.send_message(
                            msg.from_agent,
                            'result',
                            {'task': msg.content.get('task'), 'result': result}
                        )

                        # Store result in coordination manager
                        self.coordination.store_result(self.agent_id, result)

                        self.update_status('idle')
                        print(f"[{self.agent_id}] Task completed")

                    except Exception as e:
                        error_msg = f"Error processing task: {str(e)}"
                        print(f"[{self.agent_id}] {error_msg}")
                        self.update_status('error', error=error_msg)

                        # Send error response
                        self.send_message(
                            msg.from_agent,
                            'error',
                            {'task': msg.content.get('task'), 'error': str(e)}
                        )

                elif msg.message_type == 'query':
                    # Another agent is asking a question
                    print(f"[{self.agent_id}] Received query from {msg.from_agent}")
                    self.update_status('running', 'Answering query')

                    try:
                        answer = await self.query_claude(msg.content.get('question', ''))
                        self.send_message(
                            msg.from_agent,
                            'response',
                            {'question': msg.content.get('question'), 'answer': answer}
                        )
                        self.update_status('idle')
                    except Exception as e:
                        print(f"[{self.agent_id}] Error answering query: {e}")
                        self.update_status('error', error=str(e))

                elif msg.message_type == 'shutdown':
                    print(f"[{self.agent_id}] Received shutdown signal")
                    self.running = False

            # Small sleep to prevent busy waiting
            await asyncio.sleep(0.1)

        print(f"[{self.agent_id}] Agent stopped")

    def stop(self):
        """Stop the agent gracefully."""
        self.running = False
