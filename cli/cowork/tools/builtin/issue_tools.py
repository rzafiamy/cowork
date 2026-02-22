from typing import Any
from ..base import BaseTool

class RecordIssueSolutionTool(BaseTool):
    """Tool for recording a discovered solution to a tool failure or tricky situation."""
    
    name = "record_issue_solution"
    description = "Record a solution for an issue or tool error to be used as a hint in future similar failures. Use this when you have managed to resolve a tricky error, tool call argument failure, or situation failure so you remember how to solve it next time."
    category = "SESSION_SCRATCHPAD" # It's an internal / meta tool, so SESSION_SCRATCHPAD fits well

    @property
    def parameters(self) -> dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "issue": {
                    "type": "string",
                    "description": "What went wrong? E.g. 'Tool X failed with Invalid parameter Y'",
                },
                "reason": {
                    "type": "string",
                    "description": "Why it happened? E.g. 'Parameter Y expects an absolute path instead of relative'",
                },
                "solution": {
                    "type": "string",
                    "description": "How to fix it? E.g. 'Using os.path.abspath(path) for parameter Y'",
                },
            },
            "required": ["issue", "reason", "solution"],
        }

    def execute(self, issue: str, reason: str, solution: str) -> str:
        # Import dynamically to avoid circular dependencies
        from ...issues import IssueManager
        
        if not self.config:
            return "❌ No configuration available."
            
        # Get user_id from config or fallback
        user_id = self.config.get("user_id", "default_user")
        
        manager = IssueManager(user_id=user_id, config=self.config)
        triplet_id = manager.add_issue(issue, reason, solution)
        
        return f"✅ Issue recorded successfully. Future errors matching this issue will provide this solution as a hint. (ID: {triplet_id})"
