import os

import openai
import anthropic
from dotenv import load_dotenv
from google import genai
from google.genai import types

load_dotenv()


def create_chat_completion(model, messages, functions=None, function_call=None, **kwargs):
    if hasattr(openai, "ChatCompletion"):
        payload = {"model": model, "input": messages, **kwargs}
        if functions is not None:
            payload["functions"] = functions
        if function_call is not None:
            payload["function_call"] = function_call
        return openai.responses.create(**payload)
    if hasattr(openai, "OpenAI"):
        client = openai.OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
        if functions is not None:
            tools = [{"type": "function", "function": fn} for fn in functions]
            tool_choice = "auto" if function_call in (None, "auto") else {"type": "function", "function": {"name": function_call}}
            return client.responses.create(
                model=model,
                input=messages,
                tools=tools,
                tool_choice=tool_choice,
                **kwargs
            )
        
        return client.responses.create(model=model, messages=messages, **kwargs)
    raise RuntimeError("OpenAI client is not available.")


def create_anthropic_completion(model, messages, functions=None, function_call=None, **kwargs):
    client = anthropic.Anthropic(api_key=os.getenv("CLAUDE_API_KEY"))

    payload = {
        "model": model,
        "max_tokens": kwargs.pop("max_tokens", 1024),
        "messages": messages,
        **kwargs
    }

    if functions is not None:
        payload["tools"] = [{"type": "function", "function": fn} for fn in functions]
        if function_call not in (None, "auto"):
            payload["tool_choice"] = {"type": "tool", "name": function_call}

    return client.messages.create(**payload)


def create_gemini_completion(model, messages, functions=None, function_call=None, **kwargs):
    client = genai.Client(api_key=os.getenv("GEMINI_API_KEY"))

    # Convert OpenAI-style messages → Gemini contents
    contents = []
    system_instruction = None

    for msg in messages:
        role = msg["role"]
        content = msg["content"]

        if role == "system":
            system_instruction = content  # Gemini handles system prompts separately
            continue

        gemini_role = "model" if role == "assistant" else "user"
        contents.append(types.Content(
            role=gemini_role,
            parts=[types.Part(text=content)]
        ))

    # Build config, remapping OpenAI-style keys to Gemini equivalents
    config_kwargs = {**kwargs}
    if "max_tokens" in config_kwargs:
        config_kwargs["max_output_tokens"] = config_kwargs.pop("max_tokens")
    if system_instruction:
        config_kwargs["system_instruction"] = system_instruction

    if functions is not None:
        fn_declarations = [
            types.FunctionDeclaration(
                name=fn["name"],
                description=fn.get("description", ""),
                parameters=fn.get("parameters", {})
            )
            for fn in functions
        ]
        config_kwargs["tools"] = [types.Tool(function_declarations=fn_declarations)]

        if function_call not in (None, "auto"):
            config_kwargs["tool_config"] = types.ToolConfig(
                function_calling_config=types.FunctionCallingConfig(
                    mode="ANY",
                    allowed_function_names=[function_call]
                )
            )

    config = types.GenerateContentConfig(**config_kwargs)

    return client.models.generate_content(
        model=model,
        contents=contents,
        config=config
    )


def extract_message_content(response):
    try:
        if hasattr(response, "candidates"):
            candidate = response.candidates[0]
            part = candidate.content.parts[0]

            # Function call
            if hasattr(part, "function_call") and part.function_call:
                fn = part.function_call
                return {
                    "role": "assistant",
                    "content": None,
                    "tool_calls": [{
                        "name": fn.name,
                        "arguments": dict(fn.args)
                    }]
                }

            # Normal text
            return part.text

        # Anthropic Message (content is a list of blocks)
        anthropic_content = getattr(response, "content", None)
        if isinstance(anthropic_content, list):
            return "".join(
                getattr(block, "text", "") for block in anthropic_content
                if getattr(block, "type", None) == "text"
            )

        # OpenAI-style dict (other providers)
        text = getattr(response, "output_text", None)
        if text:
            return text
        # Chat Completions object
        choices = getattr(response, "choices", None)
        if choices:
            return choices[0].message.content
        # Plain dict fallback (e.g. cached or manually built responses)
        if isinstance(response, dict):
            return response.get("output_text") or \
                response.get("choices", [{}])[0].get("message", {}).get("content")
    except TypeError:
        raise ValueError(f"Unrecognised response type: {type(response)}")
    return response.get("output_text") or response.get("choices", [{}])[0].get("message", {}).get("content")


def extract_function_call(message):
    if isinstance(message, dict):
        return message.get("function_call")
    tool_calls = getattr(message, "tool_calls", None)
    if tool_calls:
        tool = tool_calls[0]
        return {"name": tool.function.name, "arguments": tool.function.arguments}
    return None
