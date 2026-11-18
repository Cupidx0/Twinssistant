"""Tool-use loop: stream a step, run any requested tools, repeat (capped)."""
from concurrent.futures import ThreadPoolExecutor

from llm import refusal_text, stream_claude, text_of
from tools import STATUS_LABELS, run_tool

MAX_STEPS = 6


def agent_turn(emit, model, system, messages, tools, ctx, think=False, effort=None,
               max_steps=MAX_STEPS, feature="chat"):
    """Run up to max_steps model calls. Mutates `messages`.

    Returns {"reply", "stop_reason", "usage": {...}, "model"}.
    """
    totals = {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0,
              "cache_creation_input_tokens": 0}
    reply_parts = []
    resp = None
    hit_step_cap = False
    for step in range(max_steps):
        resp = stream_claude(emit, model, messages, system=system, tools=tools,
                             think=think, effort=effort, user_id=ctx.user_id, feature=feature)
        for key in totals:
            totals[key] += getattr(resp.usage, key, 0) or 0
        messages.append({"role": "assistant", "content": resp.content})
        step_text = text_of(resp)
        if step_text:
            reply_parts.append(step_text)

        if resp.stop_reason == "refusal":
            reply_parts = [refusal_text(resp)]
            break
        tool_uses = [b for b in resp.content if b.type == "tool_use"]
        if resp.stop_reason != "tool_use" or not tool_uses:
            break
        if step == max_steps - 1:
            hit_step_cap = True  # don't run tools whose results nobody will read
            break

        for block in tool_uses:
            if emit:
                emit("tool", {"name": block.name, "label": STATUS_LABELS.get(block.name, block.name),
                              "input": block.input})

        def run(block):
            content, is_error = run_tool(block.name, block.input, ctx)
            return {"type": "tool_result", "tool_use_id": block.id, "content": content,
                    "is_error": is_error}

        # Parallel calls are answered together in one user message.
        if len(tool_uses) == 1:
            results = [run(tool_uses[0])]
        else:
            with ThreadPoolExecutor(max_workers=len(tool_uses)) as pool:
                results = list(pool.map(run, tool_uses))
        messages.append({"role": "user", "content": results})
        if emit:
            emit("tool_done", {"names": [b.name for b in tool_uses]})

    reply = "\n\n".join(p.strip() for p in reply_parts if p.strip())
    if resp is not None and resp.stop_reason == "max_tokens":
        reply += "\n\n_(Reply cut off at the length limit.)_"
    if hit_step_cap:
        reply += "\n\n_(Stopped after the maximum number of tool steps. Ask me to continue if needed.)_"
    return {"reply": reply or "I couldn't put together an answer for that.",
            "stop_reason": resp.stop_reason if resp else None,
            "usage": totals, "model": getattr(resp, "model", model) if resp else model}
