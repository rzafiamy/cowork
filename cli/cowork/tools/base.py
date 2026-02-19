"""
🏗️ Base Tool Interface
Defines the contract all tools must follow.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional, Callable


class BaseTool(ABC):
    """
    Base class for all Cowork tools.
    Encapsulates both the schema definition and the execution logic.
    """

    def __init__(
        self, 
        status_callback: Optional[Callable[[str], None]] = None,
        scratchpad: Any = None,
        config: Any = None,
    ) -> None:
        self.status_callback = status_callback or (lambda msg: None)
        self.scratchpad = scratchpad
        self.config = config

    def _emit(self, msg: str) -> None:
        """Helper to send status updates back to the UI."""
        self.status_callback(msg)

    @property
    @abstractmethod
    def name(self) -> str:
        """The tool name as it appears in the schema (e.g. 'calc')."""
        pass

    @property
    @abstractmethod
    def description(self) -> str:
        """A clear description of what the tool does for the LLM."""
        pass

    @property
    @abstractmethod
    def category(self) -> str:
        """The category this tool belongs to (e.g. 'DATA_AND_UTILITY')."""
        pass

    @property
    @abstractmethod
    def parameters(self) -> Dict[str, Any]:
        """
        The JSON schema for parameters (the 'parameters' object).
        Should include 'type': 'object', 'properties', and 'required'.
        """
        pass

    def to_schema(self) -> Dict[str, Any]:
        """Convert to OpenAI-style tool schema."""
        return {
            "category": self.category,
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }

    @abstractmethod
    def execute(self, **kwargs: Any) -> str:
        """
        Execute the tool logic.
        Args are passed as keyword arguments derived from the schema.
        Should return a string (result or error message).
        """
        pass
