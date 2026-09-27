import os
import shlex
import subprocess
import platform
from pathlib import Path
from mcp.server.mcpserver import MCPServer
import subprocess, pyautogui

mcp = MCPServer("system-control")

SAFE_ROOT = Path.home()
 
# Only these commands can be run via run_command. Add to this list
# deliberately — never allow arbitrary shell strings from an LLM.
ALLOWED_COMMANDS = {
    "date", "whoami", "pwd", "uptime", "df", "free",
    "git status", "git log -n 5", "git diff",
}
 
 
def _resolve_safe(path_str: str) -> Path:
    """Resolve a user-supplied path and make sure it stays under SAFE_ROOT."""
    p = (SAFE_ROOT / path_str).resolve()
    if SAFE_ROOT.resolve() not in p.parents and p != SAFE_ROOT.resolve():
        raise ValueError(f"Path '{path_str}' is outside the allowed root {SAFE_ROOT}")
    return p

@mcp.tool()
def system_info() -> dict:
    """Return basic info about the machine Twinssistant is running on."""
    return {
        "os": platform.system(),
        "os_version": platform.version(),
        "machine": platform.machine(),
        "python_version": platform.python_version(),
        "cwd": str(Path.cwd()),
        "user": os.environ.get("USER") or os.environ.get("USERNAME"),
    }
@mcp.tool()
def run_command(command: str) -> dict:
    """
    Run a whitelisted shell command and return its output.
 
    Only commands in ALLOWED_COMMANDS are permitted. This is deliberately
    restrictive — expand the whitelist as you decide what Twinssistant is
    actually allowed to do on the host machine.
 
    Args:
        command: the exact command string, must match an allowed entry.
    """
    if command not in ALLOWED_COMMANDS:
        raise PermissionError(
            f"Command '{command}' is not in the allowlist. "
            f"Allowed: {sorted(ALLOWED_COMMANDS)}"
        )
    result = subprocess.run(
        shlex.split(command),
        capture_output=True,
        text=True,
        timeout=10,
    )
    return {
        "stdout": result.stdout.strip(),
        "stderr": result.stderr.strip(),
        "returncode": result.returncode,
    }
 
@mcp.tool()
def open_app(name: str) -> str:
    """Open a macOS application by name."""
    name = "youtube" if name.lower() == "yt" else name
    subprocess.run(["open", "-a", name])
    return f"Opened {name}"

@mcp.tool()
def click_at(x: int, y: int) -> str:
    """Click the mouse at screen coordinates."""
    pyautogui.click(x, y)
    return f"Clicked at ({x},{y})"

@mcp.tool()
def read_file(subpath: str, max_chars: int = 5000) -> str:
    """
    Read a text file under SAFE_ROOT.
 
    Args:
        subpath: relative path under the safe root.
        max_chars: truncate content to this many characters (default 5000).
    """
    target = _resolve_safe(subpath)
    if not target.is_file():
        raise FileNotFoundError(f"{target} is not a file")
    text = target.read_text(errors="replace")
    if len(text) > max_chars:
        text = text[:max_chars] + f"\n...[truncated, {len(text)} chars total]"
    return text
 
# ---------------------------------------------------------------------------
# Tools
# ---------------------------------------------------------------------------
 
 
 
@mcp.tool()
def list_files(subpath: str = ".") -> list[str]:
    """
    List files and folders under SAFE_ROOT/subpath.
 
    Args:
        subpath: relative path under the safe root (default: root itself).
    """
    target = _resolve_safe(subpath)
    if not target.exists():
        raise FileNotFoundError(f"{target} does not exist")
    if not target.is_dir():
        raise NotADirectoryError(f"{target} is not a directory")
    return sorted(p.name + ("/" if p.is_dir() else "") for p in target.iterdir())
 
if __name__ == "__main__":
    mcp.run(transport="stdio")