"""
Shared coordination infrastructure for multi-agent orchestration.
Uses multiprocessing.Manager to provide shared state between agent processes.
"""
import multiprocessing as mp
from typing import Dict, Any, Optional
from dataclasses import dataclass, field
from datetime import datetime
import json


@dataclass
class AgentMessage:
    """Message passed between agents."""
    from_agent: str
    to_agent: Optional[str]  # None means broadcast
    message_type: str  # 'query', 'response', 'status', 'result'
    content: Dict[str, Any]
    timestamp: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "from_agent": self.from_agent,
            "to_agent": self.to_agent,
            "message_type": self.message_type,
            "content": self.content,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentMessage':
        return cls(
            from_agent=data["from_agent"],
            to_agent=data.get("to_agent"),
            message_type=data["message_type"],
            content=data["content"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


@dataclass
class AgentStatus:
    """Status information for an agent process."""
    agent_id: str
    agent_type: str
    status: str  # 'idle', 'running', 'waiting', 'completed', 'error'
    current_task: Optional[str] = None
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        return {
            "agent_id": self.agent_id,
            "agent_type": self.agent_type,
            "status": self.status,
            "current_task": self.current_task,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "error": self.error,
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'AgentStatus':
        return cls(
            agent_id=data["agent_id"],
            agent_type=data["agent_type"],
            status=data["status"],
            current_task=data.get("current_task"),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            completed_at=datetime.fromisoformat(data["completed_at"]) if data.get("completed_at") else None,
            error=data.get("error"),
        )


class CoordinationManager:
    """
    Central coordination manager for multi-agent system.
    Provides shared state, message queues, and locks.
    """

    def __init__(self):
        self.manager = mp.Manager()

        # Message queues for inter-agent communication
        self.message_queue = self.manager.Queue()
        self.user_input_queue = self.manager.Queue()

        # Shared state dictionaries
        self.agent_status = self.manager.dict()  # agent_id -> AgentStatus dict
        self.shared_state = self.manager.dict()  # General shared state
        self.file_locks = self.manager.dict()    # file_path -> lock owner

        # Locks for coordination
        self.state_lock = self.manager.Lock()
        self.file_lock_manager = self.manager.Lock()

        # Results storage
        self.results = self.manager.dict()  # agent_id -> results

    def create_agent_queues(self, agent_id: str) -> tuple:
        """Create dedicated input/output queues for an agent."""
        input_queue = self.manager.Queue()
        output_queue = self.manager.Queue()
        return input_queue, output_queue

    def register_agent(self, agent_id: str, agent_type: str):
        """Register a new agent in the system."""
        with self.state_lock:
            self.agent_status[agent_id] = AgentStatus(
                agent_id=agent_id,
                agent_type=agent_type,
                status='idle'
            ).to_dict()

    def update_agent_status(self, agent_id: str, status: str,
                           current_task: Optional[str] = None,
                           error: Optional[str] = None):
        """Update an agent's status."""
        with self.state_lock:
            agent_status = AgentStatus.from_dict(self.agent_status[agent_id])
            agent_status.status = status
            agent_status.current_task = current_task
            agent_status.error = error

            if status == 'running' and agent_status.started_at is None:
                agent_status.started_at = datetime.now()
            elif status in ('completed', 'error'):
                agent_status.completed_at = datetime.now()

            self.agent_status[agent_id] = agent_status.to_dict()

    def send_message(self, msg: AgentMessage):
        """Send a message to the global message queue."""
        self.message_queue.put(msg.to_dict())

    def get_message(self, agent_id: str, timeout: float = 0.1) -> Optional[AgentMessage]:
        """
        Get a message for a specific agent (or broadcast).
        Non-blocking with short timeout.
        """
        try:
            import queue
            msg_dict = self.message_queue.get(timeout=timeout)
            msg = AgentMessage.from_dict(msg_dict)

            # Check if message is for this agent or broadcast
            if msg.to_agent is None or msg.to_agent == agent_id:
                return msg
            else:
                # Put it back for another agent
                self.message_queue.put(msg_dict)
                return None
        except:
            return None

    def acquire_file_lock(self, agent_id: str, file_path: str) -> bool:
        """
        Acquire a lock on a file for an agent.
        Returns True if lock acquired, False if already locked.
        """
        with self.file_lock_manager:
            if file_path in self.file_locks:
                # Already locked by someone else
                return False
            else:
                self.file_locks[file_path] = agent_id
                return True

    def release_file_lock(self, agent_id: str, file_path: str):
        """Release a file lock."""
        with self.file_lock_manager:
            if self.file_locks.get(file_path) == agent_id:
                del self.file_locks[file_path]

    def store_result(self, agent_id: str, result: Any):
        """Store result from an agent."""
        with self.state_lock:
            self.results[agent_id] = result

    def get_result(self, agent_id: str) -> Optional[Any]:
        """Get stored result from an agent."""
        return self.results.get(agent_id)

    def get_all_agent_status(self) -> Dict[str, Dict[str, Any]]:
        """Get status of all registered agents."""
        with self.state_lock:
            return dict(self.agent_status)

    def shutdown(self):
        """Clean shutdown of coordination manager."""
        self.manager.shutdown()
