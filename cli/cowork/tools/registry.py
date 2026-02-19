"""
📂 Tool Registry
Handles discovery, registration, and lookup of all modular tools.
"""

from typing import Dict, List, Any, Optional, Type, Callable
from .base import BaseTool

class ToolRegistry:
    def __init__(self) -> None:
        self._tool_classes: Dict[str, Type[BaseTool]] = {}
        self._tool_instances: Dict[str, BaseTool] = {}

    def register(self, tool: Type[BaseTool] | BaseTool) -> None:
        """Register a tool class or instance."""
        if isinstance(tool, type):
            # It's a class
            temp_instance = tool()
            self._tool_classes[temp_instance.name] = tool
        else:
            # It's an instance
            self._tool_instances[tool.name] = tool

    def get_tool_class(self, name: str) -> Optional[Type[BaseTool]]:
        """Look up a tool class by name."""
        return self._tool_classes.get(name)

    def get_all_tool_classes(self) -> List[Type[BaseTool]]:
        """Return all registered tool classes."""
        return list(self._tool_classes.values())

    def create_instances(
        self, 
        status_callback: Optional[Callable[[str], None]] = None,
        scratchpad: Any = None,
        config: Any = None
    ) -> Dict[str, BaseTool]:
        """Create instances and return a map of name -> instance."""
        instances = {}
        # Instantiate classes
        for name, cls in self._tool_classes.items():
            instances[name] = cls(status_callback=status_callback, scratchpad=scratchpad, config=config)
        # Add already existing instances
        instances.update(self._tool_instances)
        return instances

    def get_schemas(self) -> List[Dict[str, Any]]:
        """Return all tool schemas for the LLM."""
        schemas = []
        for cls in self._tool_classes.values():
            schemas.append(cls().to_schema())
        for inst in self._tool_instances.values():
            schemas.append(inst.to_schema())
        return schemas

# Global registry instance
registry = ToolRegistry()
