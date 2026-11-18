"""Claude adapter: streaming, prompt caching, adaptive thinking, usage capture.

Notes for the 5.5 models:
- Thinking is adaptive. `{"type": "enabled", "budget_tokens": N}` is rejected,
  so "think harder" raises output_config.effort instead and shows summarised
  thinking.
- Sampling params (temperature/top_p) are not sent.
- Sonnet/Opus 5.5 requests opt into server-side refusal fallbacks.
"""
import json
import re

from costs import log_usage
from services import MODEL_CHEAP, MODEL_MAIN, anthropic_client

FALLBACK_MODELS = {"claude-sonnet-5-5", "claude-opus-5-5"}
FALLBACK_BETA = "server-side-fallback-2026-07-01"
EPHEMERAL = {"type": "ephemeral"}


def request_kwargs(model, messages, system=None, tools=None, think=False, effort=None,
                   max_tokens=16000, auto_cache=True, output_format=None):
    kw = {"model": model, "max_tokens": max_tokens, "messages": messages}
    if system:
        kw["system"] = system
    if tools:
        kw["tools"] = tools
    if think:
        kw["thinking"] = {"type": "adaptive", "display": "summarized"}
        effort = "high" if effort in (None, "low", "medium") else effort
    output_config = {}
    if effort:
        output_config["effort"] = effort
    if output_format:
        output_config["format"] = output_format
    if output_config:
        kw["output_config"] = output_config
    if auto_cache:
        # Top-level automatic caching covers the growing tail (tool loop steps).
        kw["cache_control"] = EPHEMERAL
    if model in FALLBACK_MODELS:
        kw["extra_headers"] = {"anthropic-beta": FALLBACK_BETA}
        kw["extra_body"] = {"fallbacks": "default"}
    return kw


def text_of(message):
    return "".join(b.text for b in message.content if getattr(b, "type", None) == "text")


def refusal_text(message):
    details = getattr(message, "stop_details", None)
    category = getattr(details, "category", None) if details else None
    suffix = f" ({category})" if category else ""
    return f"Sorry, I can't help with that request{suffix}."


def stream_claude(emit, model, messages, system=None, tools=None, think=False, effort=None,
                  max_tokens=16000, user_id=None, feature="chat"):
    """Stream one model call. `emit(event, payload)` receives "token" and "thinking" deltas.

    Returns the final Message (content, stop_reason, usage). Usage is logged.
    """
    kw = request_kwargs(model, messages, system=system, tools=tools, think=think,
                        effort=effort, max_tokens=max_tokens)
    with anthropic_client().messages.stream(**kw) as stream:
        for event in stream:
            if event.type != "content_block_delta" or emit is None:
                continue
            if event.delta.type == "text_delta":
                emit("token", {"text": event.delta.text})
            elif event.delta.type == "thinking_delta" and event.delta.thinking:
                emit("thinking", {"text": event.delta.thinking})
        final = stream.get_final_message()
    # A refusal fallback may answer on another model; price what actually ran.
    log_usage(user_id, getattr(final, "model", None) or model, final.usage, feature=feature)
    return final


def complete(prompt, model=None, system=None, user_id=None, feature="internal",
             max_tokens=4000, effort="low", think=False, output_format=None):
    """Non-interactive call (streamed under the hood to avoid HTTP timeouts). Returns text."""
    model = model or MODEL_CHEAP
    kw = request_kwargs(model, [{"role": "user", "content": prompt}], system=system,
                        think=think, effort=effort, max_tokens=max_tokens,
                        auto_cache=False, output_format=output_format)
    with anthropic_client().messages.stream(**kw) as stream:
        final = stream.get_final_message()
    log_usage(user_id, getattr(final, "model", None) or model, final.usage, feature=feature)
    if final.stop_reason == "refusal":
        return ""
    return text_of(final).strip()


def cheap_complete(prompt, user_id=None, feature="memory", max_tokens=2000, system=None):
    return complete(prompt, model=MODEL_CHEAP, system=system, user_id=user_id,
                    feature=feature, max_tokens=max_tokens, effort="low")


def main_complete(prompt, user_id=None, feature="writing", max_tokens=32000, think=False,
                  system=None, model=None):
    return complete(prompt, model=model or MODEL_MAIN, system=system, user_id=user_id,
                    feature=feature, max_tokens=max_tokens,
                    effort="high" if think else "medium", think=think)


def strip_code_fences(text):
    text = (text or "").strip()
    m = re.match(r"^```(?:json)?\s*(.*?)\s*```$", text, re.DOTALL)
    return m.group(1) if m else text


def parse_json(text, default=None):
    text = strip_code_fences(text)
    try:
        return json.loads(text)
    except (json.JSONDecodeError, TypeError):
        m = re.search(r"(\{.*\}|\[.*\])", text or "", re.DOTALL)
        if m:
            try:
                return json.loads(m.group(1))
            except json.JSONDecodeError:
                pass
    return default


def cheap_json(prompt, default=None, user_id=None, feature="memory", max_tokens=2000):
    text = cheap_complete(prompt + "\n\nReturn only JSON, no prose.", user_id=user_id,
                          feature=feature, max_tokens=max_tokens)
    return parse_json(text, default if default is not None else {})


# ── Prompt caching helpers ──────────────────────────────────────────────────

def build_system(system_prompt, profile_text, summary_text=""):
    """Stable content first. Breakpoint after the profile (tools + system + profile
    are cached together), a second after the summary, which changes rarely."""
    blocks = [
        {"type": "text", "text": system_prompt},
        {"type": "text", "text": f"<user_profile>\n{profile_text}\n</user_profile>",
         "cache_control": EPHEMERAL},
    ]
    if summary_text:
        blocks.append({"type": "text",
                       "text": f"<conversation_summary>\n{summary_text}\n</conversation_summary>",
                       "cache_control": EPHEMERAL})
    return blocks


def mark_cached(message):
    """Put a cache breakpoint on the last block of `message` (mutates and returns it)."""
    if isinstance(message["content"], str):
        message["content"] = [{"type": "text", "text": message["content"]}]
    message["content"][-1]["cache_control"] = EPHEMERAL
    return message
