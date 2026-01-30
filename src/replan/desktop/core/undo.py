"""
Undo/Redo system using command pattern.
"""

from typing import List, Optional, Callable, Any
from dataclasses import dataclass


@dataclass
class Command:
    """Base command class for undo/redo operations."""
    description: str
    execute: Callable[[], None]
    undo: Callable[[], None]
    
    def __call__(self):
        """Execute the command."""
        self.execute()


class UndoManager:
    """Manages undo/redo stack."""
    
    def __init__(self, max_depth: int = 50):
        """
        Initialize undo manager.
        
        Args:
            max_depth: Maximum number of commands to keep in history
        """
        self.max_depth = max_depth
        self.undo_stack: List[Command] = []
        self.redo_stack: List[Command] = []
    
    def execute(self, command: Command):
        """
        Execute a command and add it to undo stack.
        
        Args:
            command: Command to execute
        """
        command.execute()
        self.undo_stack.append(command)
        
        # Limit stack size
        if len(self.undo_stack) > self.max_depth:
            self.undo_stack.pop(0)
        
        # Clear redo stack when new command is executed
        self.redo_stack.clear()
    
    def undo(self) -> bool:
        """
        Undo the last command.
        
        Returns:
            True if undo was successful, False if no commands to undo
        """
        if not self.undo_stack:
            return False
        
        command = self.undo_stack.pop()
        command.undo()
        self.redo_stack.append(command)
        return True
    
    def redo(self) -> bool:
        """
        Redo the last undone command.
        
        Returns:
            True if redo was successful, False if no commands to redo
        """
        if not self.redo_stack:
            return False
        
        command = self.redo_stack.pop()
        command.execute()
        self.undo_stack.append(command)
        return True
    
    def can_undo(self) -> bool:
        """Check if undo is available."""
        return len(self.undo_stack) > 0
    
    def can_redo(self) -> bool:
        """Check if redo is available."""
        return len(self.redo_stack) > 0
    
    def get_undo_description(self) -> Optional[str]:
        """Get description of next command to undo."""
        if self.undo_stack:
            return self.undo_stack[-1].description
        return None
    
    def get_redo_description(self) -> Optional[str]:
        """Get description of next command to redo."""
        if self.redo_stack:
            return self.redo_stack[-1].description
        return None
    
    def clear(self):
        """Clear all undo/redo history."""
        self.undo_stack.clear()
        self.redo_stack.clear()
