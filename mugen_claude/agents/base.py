"""
Base agent class for all agent processes.
"""
import asyncio
import os
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any
from datetime import datetime
from anthropic import Anthropic

from ..coordination import CoordinationManager, AgentMessage


class BaseAgent(ABC):
    """
    Base class for all agent processes.
    Each agent runs in its own process and communicates via the coordination manager.
    """

    def __init__(
        self,
        agent_id: str,
        agent_type: str,
        coordination_manager: CoordinationManager,
        api_key: Optional[str] = None,
    ):
        """
        Initialize the base agent.

        Args:
            agent_id: Unique identifier for this agent instance
            agent_type: Type of agent (explorer, planner, executor, etc.)
            coordination_manager: Shared coordination manager
            api_key: Anthropic API key (uses ANTHROPIC_API_KEY env var if not provided)
        """
        self.agent_id = agent_id
        self.agent_type = agent_type
        self.coordination = coordination_manager
        self.running = False

        # Initialize Claude client
        api_key = api_key or os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            raise ValueError("ANTHROPIC_API_KEY not found in environment")
        self.client = Anthropic(api_key=api_key)

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

    async def query_claude(self, user_message: str, max_tokens: int = 4096) -> str:
        """
        Send a query to Claude and get a response.

        Args:
            user_message: The user message to send
            max_tokens: Maximum tokens in response

        Returns:
            Claude's response text
        """
        # Add user message to history
        self.conversation_history.append({
            "role": "user",
            "content": user_message
        })

        # Call Claude API
        response = self.client.messages.create(
            model="claude-sonnet-4-5-20250929",
            max_tokens=max_tokens,
            system=self.get_system_prompt(),
            messages=self.conversation_history
        )

        # Extract response text
        response_text = ""
        for block in response.content:
            if hasattr(block, 'text'):
                response_text += block.text

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
