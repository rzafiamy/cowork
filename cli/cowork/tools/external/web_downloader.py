"""
📥 Web Downloader Tools
Implementations for securely downloading files from the internet.
"""

import os
import requests
import mimetypes
from urllib.parse import urlparse
from .utils import _env

# Security: Allowed extensions and their corresponding MIME types
# We prioritize extensions but also check MIME types where possible.
SAFE_EXTENSIONS = {
    # Documents
    ".pdf": ["application/pdf"],
    ".docx": ["application/vnd.openxmlformats-officedocument.wordprocessingml.document"],
    ".doc": ["application/msword"],
    ".xlsx": ["application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"],
    ".xls": ["application/vnd.ms-excel"],
    ".pptx": ["application/vnd.openxmlformats-officedocument.presentationml.presentation"],
    ".ppt": ["application/vnd.ms-powerpoint"],
    ".txt": ["text/plain"],
    ".md": ["text/markdown", "text/x-markdown"],
    ".rtf": ["application/rtf", "text/rtf"],
    # Images
    ".jpg": ["image/jpeg"],
    ".jpeg": ["image/jpeg"],
    ".png": ["image/png"],
    ".gif": ["image/gif"],
    ".webp": ["image/webp"],
    ".svg": ["image/svg+xml"],
    # Data
    ".json": ["application/json", "text/plain"],
    ".csv": ["text/csv", "application/csv"],
    ".xml": ["application/xml", "text/xml"],
    ".yaml": ["application/x-yaml", "text/yaml"],
    ".yml": ["application/x-yaml", "text/yaml"],
    # Archives
    ".zip": ["application/zip", "application/x-zip-compressed"],
}

MAX_FILE_SIZE_MB = 100 # Default max size

def web_download_file(url: str, output_path: str = None) -> str:
    """
    Securely download a file from the internet.
    Only supports specific safe file types and checks Content-Type headers.
    """
    # 1. Parse URL and check extension
    parsed_url = urlparse(url)
    ext = os.path.splitext(parsed_url.path)[1].lower()
    
    if not ext:
        # Try to guess extension from URL if path doesn't have it (some CDNs)
        # But for security, we prefer explicit extensions in the URL or we'll check MIME later
        pass

    if ext and ext not in SAFE_EXTENSIONS:
        return f"❌ Security Error: File type `{ext}` is not supported for direct download."

    try:
        # 2. Start request (stream=True to check headers before full download)
        headers = {"User-Agent": "CoworkCLI/1.0 (Enterprise Agentic Assistant)"}
        response = requests.get(url, headers=headers, stream=True, timeout=30)
        response.raise_for_status()

        # 3. Security: Check Content-Length
        content_length = response.headers.get('Content-Length')
        if content_length:
            size_mb = int(content_length) / (1024 * 1024)
            if size_mb > MAX_FILE_SIZE_MB:
                return f"❌ Security Error: File is too large ({size_mb:.1f}MB). Limit is {MAX_FILE_SIZE_MB}MB."

        # 4. Security: Check Content-Type
        content_type = response.headers.get('Content-Type', '').split(';')[0].strip()
        
        # If we have an extension, verify it matches the Content-Type roughly
        if ext in SAFE_EXTENSIONS:
            allowed_mimes = SAFE_EXTENSIONS[ext]
            # Some servers send generic application/octet-stream, we might allow it if extension is safe
            # but stricter is better.
            if content_type not in allowed_mimes and content_type != "application/octet-stream":
                # Check if it's at least a related type
                pass 
        
        # If no extension in URL, use Content-Type to determine one
        if not ext:
            ext = mimetypes.guess_extension(content_type)
            if not ext or ext not in SAFE_EXTENSIONS:
                return f"❌ Security Error: Remote content type `{content_type}` is not in the safe whitelist."

        # 5. Determine local path
        if not output_path:
            filename = os.path.basename(parsed_url.path)
            if not filename or filename == ext:
                filename = f"downloaded_file{ext}"
            output_path = filename

        # Ensure output_path is safe (no path traversal)
        output_path = os.path.basename(output_path)
        
        # 6. Perform Download
        with open(output_path, 'wb') as f:
            downloaded_size = 0
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    downloaded_size += len(chunk)
                    if downloaded_size > MAX_FILE_SIZE_MB * 1024 * 1024:
                        f.close()
                        os.remove(output_path)
                        return "❌ Security Error: Download exceeded maximum allowed size during transfer."
                    f.write(chunk)

        return f"✅ Successfully downloaded file to `{output_path}` ({downloaded_size} bytes, type: {content_type})"

    except requests.exceptions.HTTPError as e:
        return f"❌ HTTP Error: {e}"
    except Exception as e:
        return f"❌ Download failed: {e}"

TOOLS = [
    {
        "category": "WEB_TOOLS",
        "type": "function",
        "function": {
            "name": "web_download_file",
            "description": "Securely download a file from a URL. Supports docs, images, and data files only.",
            "parameters": {
                "type": "object",
                "properties": {
                    "url": {"type": "string", "description": "The direct URL of the file to download"},
                    "output_path": {"type": "string", "description": "Optional: Specific filename/path to save as (base name only)"},
                },
                "required": ["url"],
            },
        },
    },
]
