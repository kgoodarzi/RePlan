"""WebSocket collaboration foundation for real-time multi-user editing."""

from typing import Dict, List, Optional, Callable
from dataclasses import dataclass, asdict
import json
from enum import Enum


class OperationType(Enum):
    """Types of operations that can be synchronized."""
    OBJECT_CREATE = "object_create"
    OBJECT_UPDATE = "object_update"
    OBJECT_DELETE = "object_delete"
    PAGE_CREATE = "page_create"
    PAGE_DELETE = "page_delete"
    CATEGORY_UPDATE = "category_update"


@dataclass
class CollaborationMessage:
    """Message for collaboration synchronization."""
    operation: OperationType
    user_id: str
    timestamp: float
    data: dict
    
    def to_dict(self) -> dict:
        """Serialize to dictionary."""
        return {
            "operation": self.operation.value,
            "user_id": self.user_id,
            "timestamp": self.timestamp,
            "data": self.data
        }
    
    @classmethod
    def from_dict(cls, data: dict) -> "CollaborationMessage":
        """Deserialize from dictionary."""
        return cls(
            operation=OperationType(data["operation"]),
            user_id=data["user_id"],
            timestamp=data["timestamp"],
            data=data["data"]
        )


class CollaborationClient:
    """
    WebSocket client for real-time collaboration.
    
    This is a foundation class - full implementation requires WebSocket server.
    """
    
    def __init__(self, server_url: str = None, user_id: str = None):
        """
        Initialize collaboration client.
        
        Args:
            server_url: WebSocket server URL (e.g., "ws://localhost:8080")
            user_id: Unique user identifier
        """
        self.server_url = server_url
        self.user_id = user_id or "user_unknown"
        self.connected = False
        self.message_handlers: Dict[OperationType, List[Callable]] = {}
    
    def connect(self) -> bool:
        """
        Connect to collaboration server.
        
        Returns:
            True if connected successfully
        """
        # TODO: Implement WebSocket connection
        # This is a foundation - requires websocket library and server
        print(f"Collaboration: Would connect to {self.server_url}")
        self.connected = True
        return True
    
    def disconnect(self):
        """Disconnect from server."""
        self.connected = False
    
    def send_message(self, message: CollaborationMessage) -> bool:
        """
        Send a collaboration message.
        
        Args:
            message: Message to send
            
        Returns:
            True if sent successfully
        """
        if not self.connected:
            return False
        
        # TODO: Implement WebSocket send
        print(f"Collaboration: Would send {message.operation.value}")
        return True
    
    def register_handler(self, operation: OperationType, handler: Callable):
        """
        Register a handler for a specific operation type.
        
        Args:
            operation: Operation type to handle
            handler: Callback function(message: CollaborationMessage)
        """
        if operation not in self.message_handlers:
            self.message_handlers[operation] = []
        self.message_handlers[operation].append(handler)
    
    def _handle_message(self, message: CollaborationMessage):
        """Handle incoming message."""
        handlers = self.message_handlers.get(message.operation, [])
        for handler in handlers:
            try:
                handler(message)
            except Exception as e:
                print(f"Error in collaboration handler: {e}")
