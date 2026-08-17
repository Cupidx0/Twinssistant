from mcp.server.fastmcp import FastMCP
import subprocess, pyautogui

mcp = FastMCP("system-control")

@mcp.tool()
def run_shell(command: str) -> str:
    """Run a shell command and return output."""
    result = subprocess.run(command, shell=True, capture_output=True, text=True, timeout=30)
    return result.stdout + result.stderr

@mcp.tool()
def open_app(name: str) -> str:
    """Open a macOS application by name."""
    subprocess.run(["open", "-a", name])
    return f"Opened {name}"

@mcp.tool()
def click_at(x: int, y: int) -> str:
    """Click the mouse at screen coordinates."""
    pyautogui.click(x, y)
    return f"Clicked at ({x},{y})"

@mcp.tool()
def read_file(path: str) -> str:
    """Read a text file's contents."""
    with open(path) as f:
        return f.read()

if __name__ == "__main__":
    mcp.run()