"""
Wrapped External Tools
Adapts external tool functions to the modular BaseTool interface.
"""

from typing import Any, Dict, Callable
from ..base import BaseTool

class ExternalToolAdapter(BaseTool):
    """
    Wraps existing external tool functions into the new modular interface.
    """

    def __init__(
        self, 
        schema: Dict[str, Any], 
        handler: Callable[..., str], 
        **kwargs
    ) -> None:
        super().__init__(**kwargs)
        self._schema = schema
        self._handler = handler

    @property
    def name(self) -> str:
        return self._schema["function"]["name"]

    @property
    def description(self) -> str:
        return self._schema["function"]["description"]

    @property
    def category(self) -> str:
        return self._schema["category"]

    @property
    def parameters(self) -> Dict[str, Any]:
        return self._schema["function"]["parameters"]

    def execute(self, **kwargs) -> str:
        # Note: We don't call self._emit here because the handlers 
        # often have their own emission logic or are simple.
        # But we could wrap them if needed.
        return self._handler(**kwargs)
