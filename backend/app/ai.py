import os
from typing import Any

import httpx

OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL = "openai/gpt-oss-120b"


def _extract_text(payload: dict[str, Any]) -> str:
    choices = payload.get("choices")
    if not choices:
        raise ValueError("No choices returned from OpenRouter")
    message = choices[0].get("message", {})
    content = message.get("content")
    if isinstance(content, str):
        return content.strip()
    if isinstance(content, list):
        text_parts: list[str] = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                text_parts.append(str(item.get("text", "")))
        merged = "".join(text_parts).strip()
        if merged:
            return merged
    raise ValueError("OpenRouter response did not contain text content")


def send_chat_prompt(prompt: str, api_key: str) -> str:
    return send_chat_messages(
        [{"role": "user", "content": prompt}],
        api_key,
    )


def send_chat_messages(messages: list[dict[str, str]], api_key: str) -> str:
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    body = {
        "model": OPENROUTER_MODEL,
        "messages": messages,
    }
    with httpx.Client(timeout=30) as client:
        response = client.post(OPENROUTER_URL, headers=headers, json=body)
        response.raise_for_status()
    return _extract_text(response.json())


def run_smoke_test() -> str:
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is missing")
    return send_chat_messages(
        [{"role": "user", "content": "What is 2+2? Reply with just the final answer."}],
        api_key,
    )


def send_chat_messages_with_env(messages: list[dict[str, str]]) -> str:
    api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
    if not api_key:
        raise ValueError("OPENROUTER_API_KEY is missing")
    return send_chat_messages(messages, api_key)
