"""
🎬 Media Tools
YouTube downloading and audio/video conversion using yt-dlp and ffmpeg.
"""

import os
import subprocess
from pathlib import Path
from typing import Any, Dict

from ..base import BaseTool
from ...workspace import workspace_manager, WORKSPACE_ROOT

def _get_artifacts_dir(scratchpad) -> Path:
    if scratchpad:
        for info in workspace_manager.list_all():
            if info["session_id"] == scratchpad.session_id:
                from ...workspace import WorkspaceSession
                ws = WorkspaceSession.load(info["slug"])
                if ws:
                    return ws.artifacts_path
    return WORKSPACE_ROOT / "artifacts"

class YoutubeDownloadTool(BaseTool):
    """
    Download YouTube video into video or audio using yt-dlp.
    """
    @property
    def name(self) -> str:
        return "youtube_download"

    @property
    def description(self) -> str:
        return "Download YouTube video into video or audio using yt-dlp."

    @property
    def category(self) -> str:
        return "MULTIMODAL_TOOLS"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "url": {
                    "type": "string", 
                    "description": "YouTube URL to download."
                },
                "format": {
                    "type": "string", 
                    "description": "'video' or 'audio' (default is 'video')."
                },
            },
            "required": ["url"],
        }

    def execute(self, url: str, format: str = "video") -> str:
        artifacts_dir = _get_artifacts_dir(self.scratchpad)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        self._emit(f"📥 Downloading {url} as {format}...")
        
        cmd = ["yt-dlp", url]
        if format == "audio":
            cmd.extend(["-x", "--audio-format", "mp3"])
            cmd.extend(["-o", f"{artifacts_dir}/%(title)s.%(ext)s"])
        else:
            cmd.extend(["-f", "bestvideo[ext=mp4]+bestaudio[ext=m4a]/best[ext=mp4]/best"])
            cmd.extend(["-o", f"{artifacts_dir}/%(title)s.%(ext)s"])
            
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            # Find output file path from stdout if possible
            return f"✅ Download complete!\n\nOutput log:\n{result.stdout[-1000:]}"
        except subprocess.CalledProcessError as e:
            return f"❌ Download failed:\n{e.stderr}"
        except Exception as e:
            return f"❌ Error: {e}"

class MediaConvertTool(BaseTool):
    """
    Convert media (audio/video) from one format to another using ffmpeg.
    """
    @property
    def name(self) -> str:
        return "media_convert"

    @property
    def description(self) -> str:
        return "Convert media (audio/video) from one format to another using ffmpeg."

    @property
    def category(self) -> str:
        return "MULTIMODAL_TOOLS"

    @property
    def parameters(self) -> Dict[str, Any]:
        return {
            "type": "object",
            "properties": {
                "input_file": {
                    "type": "string", 
                    "description": "Absolute or workspace-relative path to input file."
                },
                "output_format": {
                    "type": "string", 
                    "description": "Target format extension (e.g., 'mp3', 'wav', 'mp4')."
                },
            },
            "required": ["input_file", "output_format"],
        }

    def execute(self, input_file: str, output_format: str) -> str:
        artifacts_dir = _get_artifacts_dir(self.scratchpad)
        artifacts_dir.mkdir(parents=True, exist_ok=True)
        
        input_path = Path(input_file)
        if not input_path.is_absolute():
            input_path = WORKSPACE_ROOT / input_file
            
        if not input_path.exists():
            return f"❌ Input file not found: {input_path}"
            
        output_name = f"{input_path.stem}.{output_format.lstrip('.')}"
        output_path = artifacts_dir / output_name
        
        self._emit(f"🔄 Converting {input_path.name} to {output_format}...")
        
        cmd = ["ffmpeg", "-i", str(input_path), str(output_path), "-y"]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, check=True)
            return f"✅ Conversion complete!\nSaved to: {output_path}"
        except subprocess.CalledProcessError as e:
            return f"❌ Conversion failed:\n{e.stderr}"
        except Exception as e:
            return f"❌ Error: {e}"
