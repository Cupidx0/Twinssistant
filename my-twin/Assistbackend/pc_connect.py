import subprocess
import platform
import os

def open_app(app_name: str) -> dict:
    """Launch a Mac application by name."""
    try:
        subprocess.run(["open", "-a", app_name], check=True)
        return {"success": True, "message": f"Opened {app_name}"}
    except subprocess.CalledProcessError as e:
        return {"success": False, "error": str(e)}

def list_files(directory: str) -> dict:
    """List files in a given directory."""
    try:
        entries = os.listdir(os.path.expanduser(directory))
        return {"success": True, "files": entries}
    except FileNotFoundError as e:
        return {"success": False, "error": str(e)}

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