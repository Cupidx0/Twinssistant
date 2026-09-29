import subprocess
import platform
import os
Alias_Names = {
    "camera": "Photo Booth"
}
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
        entries = os.listdir(os.path.expanduser(directory))
        return {"success": True, "files": entries}
    except FileNotFoundError as e:
        return {"success": False, "error": str(e)}
    
def open_url(url: str) -> dict:
    """Open a URL in the default web browser."""
    result = subprocess.run(["open", url], capture_output=True, text=True)
    if result.returncode == 0:
        return {"success": True, "message": f"Opened {url}"}
    return {"success": False, "error": f"Couldn't open {url}"}

def read_file(path: str, max_chars: int = 5000) -> dict:
    """Read a text file's content, capped for safety."""
    try:
        with open(os.path.expanduser(path), "r", encoding="utf-8") as f:
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
        subprocess.run(
            ["osascript", "-e", f'quit app "{app_name}"'],
            check=True
        )
        return {"success": True, "message": f"Closed {app_name}"}
    except subprocess.CalledProcessError as e:
        return {"success": False, "error": str(e)}