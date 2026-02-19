"""
🛠️ Tool System
Modular tool architecture with class-based interfaces.
"""

from .registry import registry
from .base import BaseTool

# Import builtin tools
from .builtin.utility import CalcTool, GetTimeTool, GenDiagramTool
from .builtin.scratchpad import (
    ScratchpadSaveTool, 
    ScratchpadListTool, 
    ScratchpadReadChunkTool, 
    ScratchpadSearchTool,
    ScratchpadUpdateGoalTool,
)
from .builtin.workspace import (
    WorkspaceWriteTool, 
    WorkspaceReadTool, 
    WorkspaceListTool, 
    WorkspaceNoteTool, 
    WorkspaceContextUpdateTool, 
    WorkspaceSearchTool
)
from .builtin.cron import (
    CronScheduleTool, 
    CronListTool, 
    CronDeleteTool
)
from .builtin.connectors import (
    NotesCreateTool, 
    KanbanAddTaskTool, 
    StorageWriteTool, 
    GetWeatherTool
)
from .builtin.document import (
    DocumentCreatePdfTool,
    DocumentCreatePptxTool,
    DocumentCreateXlsxTool,
    DocumentCreateDocxTool,
)
from .builtin.multimodal import (
    VisionAnalyzeTool,
    ImageGenerateTool,
    SpeechToTextTool,
    TextToSpeechTool,
)

# Register builtin tools
def _register_builtin():
    # ... previous registrations ...
    registry.register(CalcTool)
    registry.register(GetTimeTool)
    registry.register(GenDiagramTool)
    registry.register(ScratchpadSaveTool)
    registry.register(ScratchpadListTool)
    registry.register(ScratchpadReadChunkTool)
    registry.register(ScratchpadSearchTool)
    registry.register(ScratchpadUpdateGoalTool)
    registry.register(WorkspaceWriteTool)
    registry.register(WorkspaceReadTool)
    registry.register(WorkspaceListTool)
    registry.register(WorkspaceNoteTool)
    registry.register(WorkspaceContextUpdateTool)
    registry.register(WorkspaceSearchTool)
    registry.register(CronScheduleTool)
    registry.register(CronListTool)
    registry.register(CronDeleteTool)
    registry.register(NotesCreateTool)
    registry.register(KanbanAddTaskTool)
    registry.register(StorageWriteTool)
    registry.register(GetWeatherTool)
    registry.register(DocumentCreatePdfTool)
    registry.register(DocumentCreatePptxTool)
    registry.register(DocumentCreateXlsxTool)
    registry.register(DocumentCreateDocxTool)
    registry.register(VisionAnalyzeTool)
    registry.register(ImageGenerateTool)
    registry.register(SpeechToTextTool)
    registry.register(TextToSpeechTool)

def _register_external():
    from .external.adapter import ExternalToolAdapter
    from .external.implementations import EXTERNAL_TOOLS, EXTERNAL_TOOL_HANDLERS
    
    for tool_schema in EXTERNAL_TOOLS:
        name = tool_schema["function"]["name"]
        handler = EXTERNAL_TOOL_HANDLERS.get(name)
        if handler:
            # We wrap it in an adapter instance. 
            # Note: External tools don't currently use the dependencies passed to __init__,
            # but they follow the BaseTool interface now.
            registry.register(ExternalToolAdapter(tool_schema, handler))

_register_builtin()
_register_external()

# Export everything from manager for backward compatibility
from .manager import (
    ALL_TOOLS,
    CATEGORY_TOOL_MAP,
    TOOL_BY_NAME,
    EXTERNAL_CATEGORIES,
    get_tools_for_categories,
    get_available_tools_for_categories,
    get_all_available_tools,
    ExecutionGateway,
    ToolExecutor
)
