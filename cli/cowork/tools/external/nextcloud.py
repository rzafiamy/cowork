"""
☁️ Nextcloud Tools
Implementations for interacting with a Nextcloud instance via WebDAV.
"""

import os
import urllib.parse
from xml.etree import ElementTree
from .utils import _env, _missing_key

def _get_nc_credentials():
    url = _env("NEXTCLOUD_URL")
    dav_url = _env("NEXTCLOUD_WEBDAV_URL")
    user = _env("NEXTCLOUD_USER")
    password = _env("NEXTCLOUD_PASSWORD")

    if not dav_url and not url:
        return None, _missing_key("nextcloud", "NEXTCLOUD_URL or NEXTCLOUD_WEBDAV_URL")
    if not user:
        return None, _missing_key("nextcloud", "NEXTCLOUD_USER")
    if not password:
        return None, _missing_key("nextcloud", "NEXTCLOUD_PASSWORD")
    
    return {
        "url": url.rstrip('/') if url else None,
        "dav_url": dav_url.rstrip('/') if dav_url else None,
        "user": user,
        "password": password
    }, None

def _get_webdav_url(creds, path=""):
    path = path.lstrip('/')
    encoded_path = urllib.parse.quote(path)
    
    if creds["dav_url"]:
        base = creds["dav_url"]
        return f"{base}/{encoded_path}" if encoded_path else base
    
    # Fallback to standard Nextcloud structure
    base_url = creds["url"]
    user = creds["user"]
    return f"{base_url}/remote.php/dav/files/{user}/{encoded_path}"

def nextcloud_list(path: str = "") -> str:
    """
    List contents of a Nextcloud directory.
    Requires: NEXTCLOUD_URL, NEXTCLOUD_USER, NEXTCLOUD_PASSWORD
    """
    creds, err = _get_nc_credentials()
    if err: return err
    dav_url = _get_webdav_url(creds, path)
    user, password = creds["user"], creds["password"]

    try:
        import requests
    except ImportError:
        return "❌ `requests` is not installed. Run: pip install requests"

    try:
        # PROPFIND with Depth 1 to get contents
        headers = {'Depth': '1'}
        response = requests.request("PROPFIND", dav_url, auth=(user, password), headers=headers, timeout=15)
        
        if response.status_code == 404:
            return f"Path not found: {path}"
        response.raise_for_status()
        
        # Parse WebDAV XML response
        root = ElementTree.fromstring(response.content)
        lines = [f"📁 **Nextcloud Directory Listing**: `/{path}`\n"]
        
        # NS map for WebDAV
        ns = {'d': 'DAV:'}
        
        responses = root.findall('d:response', ns)
        if not responses:
            return "Empty directory."
            
        for i, resp in enumerate(responses):
            href = resp.find('d:href', ns)
            if href is None: continue
            item_path = urllib.parse.unquote(href.text or "").rstrip('/')
            
            # Skip the directory itself (which is the first response usually)
            if i == 0: continue
            
            propstat = resp.find('d:propstat', ns)
            if propstat is None: continue
            prop = propstat.find('d:prop', ns)
            if prop is None: continue
            
            resourcetype = prop.find('d:resourcetype', ns)
            is_dir = resourcetype is not None and resourcetype.find('d:collection', ns) is not None
            
            contentlength = prop.find('d:getcontentlength', ns)
            size = contentlength.text if contentlength is not None else "0"
            
            lastmodified = prop.find('d:getlastmodified', ns)
            mtime = lastmodified.text if lastmodified is not None else "Unknown"
            
            item_name = os.path.basename(item_path)
            
            icon = "📁" if is_dir else "📄"
            lines.append(f"{icon} **{item_name}**")
            lines.append(f"   Size: {size} bytes | Modified: {mtime}")
            
        return "\n".join(lines)
    except Exception as e:
        return f"Nextcloud list failed: {e}"

def nextcloud_upload(local_path: str, remote_path: str) -> str:
    """
    Upload a local file to Nextcloud.
    """
    creds, err = _get_nc_credentials()
    if err: return err
    dav_url = _get_webdav_url(creds, remote_path)
    user, password = creds["user"], creds["password"]

    try:
        import requests
    except ImportError:
        return "❌ `requests` is not installed."

    if not os.path.exists(local_path):
        return f"Local file not found: {local_path}"

    try:
        with open(local_path, 'rb') as f:
            response = requests.put(dav_url, data=f, auth=(user, password), timeout=60)
            response.raise_for_status()
        return f"✅ Successfully uploaded `{local_path}` to Nextcloud at `{remote_path}`"
    except Exception as e:
        return f"Nextcloud upload failed: {e}"

def nextcloud_download(remote_path: str, local_path: str) -> str:
    """
    Download a file from Nextcloud.
    """
    creds, err = _get_nc_credentials()
    if err: return err
    dav_url = _get_webdav_url(creds, remote_path)
    user, password = creds["user"], creds["password"]

    try:
        import requests
    except ImportError:
        return "❌ `requests` is not installed."

    try:
        response = requests.get(dav_url, auth=(user, password), stream=True, timeout=60)
        
        if response.status_code == 404:
            return f"Remote file not found: {remote_path}"
        response.raise_for_status()
        
        with open(local_path, 'wb') as f:
            for chunk in response.iter_content(chunk_size=8192):
                f.write(chunk)
        return f"✅ Successfully downloaded Nextcloud `{remote_path}` to `{local_path}`"
    except Exception as e:
        return f"Nextcloud download failed: {e}"

def nextcloud_create_folder(path: str) -> str:
    """
    Create a folder in Nextcloud.
    """
    creds, err = _get_nc_credentials()
    if err: return err
    dav_url = _get_webdav_url(creds, path)
    user, password = creds["user"], creds["password"]

    try:
        import requests
    except ImportError:
        return "❌ `requests` is not installed."

    try:
        response = requests.request("MKCOL", dav_url, auth=(user, password), timeout=15)
        if response.status_code == 405:
            return f"Folder already exists: {path}"
        response.raise_for_status()
        return f"✅ Successfully created folder: `{path}`"
    except Exception as e:
        return f"Nextcloud folder creation failed: {e}"

def nextcloud_delete(path: str) -> str:
    """
    Delete a file or folder in Nextcloud.
    """
    creds, err = _get_nc_credentials()
    if err: return err
    dav_url = _get_webdav_url(creds, path)
    user, password = creds["user"], creds["password"]

    try:
        import requests
    except ImportError:
        return "❌ `requests` is not installed."

    try:
        response = requests.delete(dav_url, auth=(user, password), timeout=15)
        if response.status_code == 404:
            return f"Path not found: {path}"
        response.raise_for_status()
        return f"✅ Successfully deleted `{path}`"
    except Exception as e:
        return f"Nextcloud delete failed: {e}"

def nextcloud_search(query: str) -> str:
    """
    Search files in Nextcloud (requires Nextcloud 20+ with Search API).
    """
    creds, err = _get_nc_credentials()
    if err: return err
    url = creds["url"]
    user, password = creds["user"], creds["password"]
    
    if not url:
        return "❌ Search requires `NEXTCLOUD_URL` (OCS Search API is not available on raw WebDAV URLs)."
    
    try:
        import requests
    except ImportError:
        return "❌ `requests` is not installed."
        
    search_url = f"{url}/ocs/v2.php/search/providers/files/search"
    params = {'term': query}
    headers = {'OCS-APIRequest': 'true', 'Accept': 'application/json'}
    
    try:
        response = requests.get(search_url, params=params, auth=(user, password), headers=headers, timeout=15)
        response.raise_for_status()
        
        data = response.json()
        entries = data.get('ocs', {}).get('data', {}).get('entries', [])
        
        if not entries:
            return f"No Nextcloud results found for: '{query}'"
            
        lines = [f"🔍 **Nextcloud Search Results for**: `{query}`\n"]
        for entry in entries:
            title = entry.get('title', 'Unknown')
            subline = entry.get('subline', '')
            lines.append(f"- **{title}** ({subline})")
            
        return "\n".join(lines)
    except Exception as e:
        return f"Nextcloud search failed: {e}"

TOOLS = [
    {
        "category": "NEXTCLOUD_TOOLS",
        "type": "function",
        "function": {
            "name": "nextcloud_list",
            "description": "List contents of a Nextcloud directory.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to list (default: root '/')"},
                },
                "required": [],
            },
        },
    },
    {
        "category": "NEXTCLOUD_TOOLS",
        "type": "function",
        "function": {
            "name": "nextcloud_upload",
            "description": "Upload a local file to Nextcloud.",
            "parameters": {
                "type": "object",
                "properties": {
                    "local_path": {"type": "string", "description": "Absolute path to local file"},
                    "remote_path": {"type": "string", "description": "Destination path in Nextcloud"},
                },
                "required": ["local_path", "remote_path"],
            },
        },
    },
    {
        "category": "NEXTCLOUD_TOOLS",
        "type": "function",
        "function": {
            "name": "nextcloud_download",
            "description": "Download a file from Nextcloud to local machine.",
            "parameters": {
                "type": "object",
                "properties": {
                    "remote_path": {"type": "string", "description": "Path of the file in Nextcloud"},
                    "local_path": {"type": "string", "description": "Destination local absolute path"},
                },
                "required": ["remote_path", "local_path"],
            },
        },
    },
    {
        "category": "NEXTCLOUD_TOOLS",
        "type": "function",
        "function": {
            "name": "nextcloud_create_folder",
            "description": "Create a new folder in Nextcloud.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path of the new folder"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "category": "NEXTCLOUD_TOOLS",
        "type": "function",
        "function": {
            "name": "nextcloud_delete",
            "description": "Delete a file or folder from Nextcloud.",
            "parameters": {
                "type": "object",
                "properties": {
                    "path": {"type": "string", "description": "Path to delete in Nextcloud"},
                },
                "required": ["path"],
            },
        },
    },
    {
        "category": "NEXTCLOUD_TOOLS",
        "type": "function",
        "function": {
            "name": "nextcloud_search",
            "description": "Search for files in Nextcloud.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {"type": "string", "description": "Search term"},
                },
                "required": ["query"],
            },
        },
    },
]
