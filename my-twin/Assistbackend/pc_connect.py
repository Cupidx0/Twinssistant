import subprocess
import platform
import os
from pathlib import Path
from urllib.parse import urlparse
Alias_Names = {
    "camera": "Photo Booth"
}
# File tools are jailed to the home folder, and hidden files/folders
# (.ssh, .env, .aws, ...) are never readable.
SAFE_ROOT = Path.home().resolve()

def _resolve_safe(path_str: str) -> Path:
    """Resolve a user/LLM-supplied path and make sure it stays under SAFE_ROOT."""
    p = (SAFE_ROOT / os.path.expanduser(path_str)).resolve()
    if p != SAFE_ROOT and SAFE_ROOT not in p.parents:
        raise PermissionError(f"'{path_str}' is outside your home folder")
    if any(part.startswith(".") for part in p.relative_to(SAFE_ROOT).parts):
        raise PermissionError(f"'{path_str}' is a hidden file or folder")
    return p

def open_app(app_name: str) -> dict:
    """Launch a Mac application by name."""
    try:
        real_app_name = Alias_Names.get(app_name.lower(), app_name)
        result = subprocess.run(["open", "-a", real_app_name], check=True)
        if result.returncode == 0:
            return {"success": True, "message": f"Opened {real_app_name}"}
        return {"success": False, "error": f"Failed to open {real_app_name}"}
    except subprocess.CalledProcessError as e:
        return {"success": False, "error": str(e)}

def list_files(directory: str) -> dict:
    """List files in a given directory."""
    try:
        entries = os.listdir(_resolve_safe(directory))
        return {"success": True, "files": [e for e in entries if not e.startswith(".")]}
    except (FileNotFoundError, NotADirectoryError, PermissionError) as e:
        return {"success": False, "error": str(e)}

def open_url(url: str) -> dict:
    """Open a URL in the default web browser."""
    # Only web links: `open` would otherwise launch file://, app-specific schemes, etc.
    if urlparse(url).scheme not in ("http", "https"):
        return {"success": False, "error": "Only http(s) links can be opened"}
    result = subprocess.run(["open", url], capture_output=True, text=True)
    if result.returncode == 0:
        return {"success": True, "message": f"Opened {url}"}
    return {"success": False, "error": f"Couldn't open {url}"}

def read_file(path: str, max_chars: int = 5000) -> dict:
    """Read a text file's content, capped for safety."""
    try:
        with open(_resolve_safe(path), "r", encoding="utf-8") as f:
            content = f.read(max_chars)
        return {"success": True, "content": content}
    except Exception as e:
        return {"success": False, "error": str(e)}

def get_system_info() -> dict:
    """Basic laptop/system info."""
    return {
        "success": True,
        "platform": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
    }
def close_app(app_name: str) -> dict:
    """Quit a Mac application by name."""
    try:
        # Pass the name as an argv item rather than formatting it into the
        # script, so a name containing quotes can't inject AppleScript.
        subprocess.run(
            ["osascript",
             "-e", "on run argv",
             "-e", "quit app (item 1 of argv)",
             "-e", "end run",
             app_name],
            check=True
        )
        return {"success": True, "message": f"Closed {app_name}"}
    except subprocess.CalledProcessError as e:
        return {"success": False, "error": str(e)}
