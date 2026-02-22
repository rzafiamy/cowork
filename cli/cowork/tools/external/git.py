"""
📂 Git Tools
Implementations for git operations (init, clone, commit, push).
"""

import subprocess
import os
from .utils import _env

def _run_git(args: list, cwd: str = ".") -> tuple[int, str, str]:
    try:
        result = subprocess.run(
            ["git"] + args,
            cwd=cwd,
            capture_output=True,
            text=True,
            timeout=60
        )
        return result.returncode, result.stdout, result.stderr
    except Exception as e:
        return -1, "", str(e)

def git_init(path: str = ".") -> str:
    """Initialize a new git repository."""
    if not os.path.exists(path):
        os.makedirs(path, exist_ok=True)
    
    code, out, err = _run_git(["init"], cwd=path)
    if code == 0:
        return f"✅ Git repository initialized at `{os.path.abspath(path)}`"
    return f"❌ Git init failed: {err or out}"

def git_clone(url: str, path: str = ".") -> str:
    """Clone a git repository."""
    # If path is '.', clone into a folder named after the repo name in the current dir
    # If path is specific, clone into that path
    args = ["clone", url]
    if path != ".":
        args.append(path)
    
    code, out, err = _run_git(args)
    if code == 0:
        return f"✅ Successfully cloned `{url}`\n{out}"
    return f"❌ Git clone failed: {err or out}"

def git_commit(message: str, path: str = ".") -> str:
    """Stage all changes and commit them."""
    # 1. Add all
    code_add, _, err_add = _run_git(["add", "."], cwd=path)
    if code_add != 0:
        return f"❌ Git add failed: {err_add}"
    
    # 2. Commit
    code_commit, out_commit, err_commit = _run_git(["commit", "-m", message], cwd=path)
    if code_commit == 0:
        return f"✅ Committed changes: {message}\n{out_commit}"
    
    if "nothing to commit" in (out_commit + err_commit).lower():
        return "ℹ️ Nothing to commit, working tree clean."
        
    return f"❌ Git commit failed: {err_commit or out_commit}"

def git_push(remote: str = "origin", branch: str = None, path: str = ".") -> str:
    """Push commits to a remote repository."""
    args = ["push", remote]
    if branch:
        args.append(branch)
        
    code, out, err = _run_git(args, cwd=path)
    if code == 0:
        return f"✅ Successfully pushed to `{remote}`\n{out or err}"
    return f"❌ Git push failed: {err or out}"

def git_status(path: str = ".") -> str:
    """Show the working tree status."""
    code, out, err = _run_git(["status"], cwd=path)
    if code == 0:
        return f"📊 **Git Status** (`{path}`)\n\n{out}"
    return f"❌ Git status failed: {err or out}"

TOOLS = [
    {
        "category": "GIT_TOOLS",
        "type": "function",
        "function": {
            "name": "git_init",
            "description": "Initialize a new git repository in the specified path.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to initialize (default: current dir)"},
                },
                "required": [],
            },
        },
    },
    {
        "category": "GIT_TOOLS",
        "type": "function",
        "function": {
            "name": "git_clone",
            "description": "Clone a git repository from a URL.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "Git repository URL"},
                    "path": {"type": "string", "description": "Destination path (optional)"},
                },
                "required": ["url"],
            },
        },
    },
    {
        "category": "GIT_TOOLS",
        "type": "function",
        "function": {
            "name": "git_commit",
            "description": "Stage all local changes and commit them with a message.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {"type": "string", "description": "Commit message"},
                    "path": {"type": "string", "description": "Repository path (default: current dir)"},
                },
                "required": ["message"],
            },
        },
    },
    {
        "category": "GIT_TOOLS",
        "type": "function",
        "function": {
            "name": "git_push",
            "description": "Push committed changes to a remote repository.",
            "parameters": {
                "type": "object",
                "properties": {
                    "remote": {"type": "string", "description": "Remote name (default: origin)"},
                    "branch": {"type": "string", "description": "Branch name (optional)"},
                    "path": {"type": "string", "description": "Repository path (default: current dir)"},
                },
                "required": [],
            },
        },
    },
    {
        "category": "GIT_TOOLS",
        "type": "function",
        "function": {
            "name": "git_status",
            "description": "Show the status of the git working tree.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Repository path (default: current dir)"},
                },
                "required": [],
            },
        },
    },
]
