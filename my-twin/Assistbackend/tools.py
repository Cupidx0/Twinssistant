"""Tool schemas and dispatcher for the agent loop (section 9 of README1).

Laptop and calendar tools act on the owner's Mac and Google account, so they
are only offered to OWNER_UIDS. Destructive laptop actions need confirmation
from the UI before they run.
"""
import json
from dataclasses import dataclass, field
from typing import Callable, Optional

from costs import log_service
from services import tavily_client

MAX_TOOL_OUTPUT = 20000

WEB_SEARCH = {
    "name": "web_search",
    "description": "Search the web for current information: news, prices, people, lyrics, weather, sports, or any fact you are unsure of. Returns titles, URLs and snippets.",
    "input_schema": {"type": "object", "properties": {
        "query": {"type": "string", "description": "Search query"}}, "required": ["query"]},
}
SEARCH_MEMORY = {
    "name": "search_memory",
    "description": "Search past conversations and saved facts about the user, including topics phrased differently. Use when the user refers to something from an earlier chat that the provided memories do not cover.",
    "input_schema": {"type": "object", "properties": {
        "query": {"type": "string", "description": "What to look for"}}, "required": ["query"]},
}
JOB_SEARCH = {
    "name": "job_search",
    "description": "Search Job Swipr for job listings.",
    "input_schema": {"type": "object", "properties": {
        "role": {"type": "string", "description": "Job title or keywords"},
        "location": {"type": "string", "description": "City or region, optional"}}, "required": ["role"]},
}
GET_CALENDAR = {
    "name": "get_calendar_events",
    "description": "Read upcoming events from the user's Google Calendar.",
    "input_schema": {"type": "object", "properties": {
        "max_results": {"type": "integer", "description": "Number of events, default 5"}}},
}
ADD_CALENDAR = {
    "name": "add_calendar_event",
    "description": "Add an event to the user's Google Calendar. Times may be natural language ('tomorrow 7pm') or ISO 8601. If no start is given the event lasts one hour before the end.",
    "input_schema": {"type": "object", "properties": {
        "summary": {"type": "string", "description": "Event title"},
        "start": {"type": "string", "description": "Start time, optional"},
        "end": {"type": "string", "description": "End time"}}, "required": ["summary", "end"]},
}
LAPTOP_ACTION = {
    "name": "laptop_action",
    "description": ("Run an approved action on the user's Mac. Only use when the user explicitly asks. "
                    "Actions and args: open_app {app_name}, close_app {app_name} (needs the user's confirmation), "
                    "list_files {directory}, read_file {path}, open_url {url}, system_info {}. "
                    "File paths are limited to the home folder. The camera app is 'Photo Booth'."),
    "input_schema": {"type": "object", "properties": {
        "action": {"type": "string", "enum": ["open_app", "close_app", "list_files", "read_file", "open_url", "system_info"]},
        "args": {"type": "object", "description": "Arguments for the action"}}, "required": ["action"]},
}

LAPTOP_ARGS = {
    "open_app": ["app_name"], "close_app": ["app_name"], "list_files": ["directory"],
    "read_file": ["path"], "open_url": ["url"], "system_info": [],
}
DESTRUCTIVE_LAPTOP_ACTIONS = {"close_app"}

STATUS_LABELS = {
    "web_search": "Searching the web",
    "search_memory": "Checking past chats",
    "job_search": "Searching jobs",
    "get_calendar_events": "Reading your calendar",
    "add_calendar_event": "Adding to your calendar",
    "laptop_action": "Working on your Mac",
}


def tools_for(is_owner):
    """Deterministic order keeps the cached prefix stable."""
    tools = [WEB_SEARCH, SEARCH_MEMORY, JOB_SEARCH]
    if is_owner:
        tools += [GET_CALENDAR, ADD_CALENDAR, LAPTOP_ACTION]
    return tools


@dataclass
class ToolContext:
    user_id: str
    is_owner: bool = False
    conv_id: Optional[str] = None
    confirm: Optional[Callable[[str, dict], bool]] = None  # returns True when the user approves
    sources: list = field(default_factory=list)
    used: list = field(default_factory=list)


def _web_search(args, ctx):
    query = str(args.get("query", "")).strip()
    if not query:
        raise ValueError("query is required")
    res = tavily_client().search(query=query, search_depth="basic", max_results=5)
    log_service(ctx.user_id, "tavily_search", 1, feature="tools")
    items = res.get("results", []) if isinstance(res, dict) else []
    out = []
    for r in items[:5]:
        source = {"title": r.get("title") or "Untitled", "url": r.get("url") or ""}
        if source["url"] and source not in ctx.sources:
            ctx.sources.append(source)
        out.append(source | {"snippet": (r.get("content") or "")[:700]})
    return out


def _search_memory(args, ctx):
    import memory
    found = memory.retrieve(ctx.user_id, str(args.get("query", "")), k=6, current_conv_id=ctx.conv_id)
    return [m["text"] for m in found] or "No matching memories."


def _job_search(args, ctx):
    from jobs import search_jobs
    result = search_jobs(str(args.get("role", "")), str(args.get("location") or ""))
    if not result.get("success"):
        raise RuntimeError(result.get("error", "job search failed"))
    jobs = result.get("jobs") or []
    return jobs[:10] if isinstance(jobs, list) else jobs


def _get_calendar(args, ctx):
    from calendar_route import get_calendar_events
    n = args.get("max_results", 5)
    n = n if isinstance(n, int) and 0 < n <= 25 else 5
    return get_calendar_events(user_id=ctx.user_id, maxResults=n)


def _add_calendar(args, ctx):
    from datetime import datetime, timedelta
    from calendar_route import add_event_to_calendar
    from utils import parse_natural_datetime
    summary = str(args.get("summary", "")).strip()
    end = parse_natural_datetime(str(args.get("end", "")))
    if not summary or not end:
        raise ValueError("Could not understand the event title or time. Ask the user to be more specific.")
    end_dt = datetime.fromisoformat(end)
    start = parse_natural_datetime(str(args.get("start"))) if args.get("start") else None
    start_dt = datetime.fromisoformat(start) if start else end_dt - timedelta(hours=1)
    add_event_to_calendar(summary, start_dt.isoformat(), end_dt.isoformat())
    return {"added": summary, "start": start_dt.isoformat(), "end": end_dt.isoformat()}


def _laptop(args, ctx):
    from Relevant_memory import handle_laptop_tool_intent
    action = args.get("action")
    if action not in LAPTOP_ARGS:
        raise ValueError(f"unknown action {action!r}")
    raw = args.get("args") or {}
    if not isinstance(raw, dict):
        raise ValueError("args must be an object")
    kwargs = {}
    for key in LAPTOP_ARGS[action]:
        if not isinstance(raw.get(key), str) or not raw[key].strip():
            raise ValueError(f"{action} needs a '{key}' string")
        kwargs[key] = raw[key]
    if action in DESTRUCTIVE_LAPTOP_ACTIONS:
        approved = ctx.confirm(action, kwargs) if ctx.confirm else False
        if not approved:
            return {"success": False, "error": "The user did not approve this action."}
    tool_name = "system_info" if action == "system_info" else action
    return handle_laptop_tool_intent(tool_name, **kwargs)


HANDLERS = {
    "web_search": (_web_search, False),
    "search_memory": (_search_memory, False),
    "job_search": (_job_search, False),
    "get_calendar_events": (_get_calendar, True),
    "add_calendar_event": (_add_calendar, True),
    "laptop_action": (_laptop, True),
}


def run_tool(name, args, ctx):
    """Returns (content_string, is_error)."""
    handler = HANDLERS.get(name)
    if not handler:
        return f"Unknown tool {name}", True
    fn, owner_only = handler
    if owner_only and not ctx.is_owner:
        return "This tool is not enabled for this account.", True
    if not isinstance(args, dict):
        return "Tool input must be an object.", True
    ctx.used.append(name)
    try:
        out = fn(args, ctx)
    except Exception as e:
        return f"{name} failed: {e}", True
    text = out if isinstance(out, str) else json.dumps(out, default=str, ensure_ascii=False)
    if len(text) > MAX_TOOL_OUTPUT:
        text = text[:MAX_TOOL_OUTPUT] + "\n[truncated]"
    return text, False
