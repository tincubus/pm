import json
from typing import Any

from pydantic import BaseModel, Field, ValidationError

SYSTEM_PROMPT = """You are an assistant for a Kanban board.
Return ONLY valid JSON with this exact top-level shape:
{
  "assistant_response": "string shown to the user",
  "board_update": {
    "rename_columns": [{"column_id": 1, "title": "New title"}],
    "create_cards": [{"column_id": 1, "title": "Card title", "details": "Card details"}],
    "update_cards": [{"card_id": 1, "title": "Card title", "details": "Card details"}],
    "move_cards": [{"card_id": 1, "target_column_id": 2, "target_position": 0}],
    "delete_cards": [1, 2]
  }
}

Rules:
- Always include "assistant_response" as a non-empty string.
- Use "board_update": null when no board changes are needed.
- Never include extra keys.
- Only refer to existing column/card IDs from the provided board JSON.
"""


class RenameColumnAction(BaseModel):
    column_id: int
    title: str = Field(min_length=1, max_length=120)


class CreateCardAction(BaseModel):
    column_id: int
    title: str = Field(min_length=1, max_length=200)
    details: str = Field(default="", max_length=5000)


class UpdateCardAction(BaseModel):
    card_id: int
    title: str = Field(min_length=1, max_length=200)
    details: str = Field(default="", max_length=5000)


class MoveCardAction(BaseModel):
    card_id: int
    target_column_id: int
    target_position: int | None = Field(default=None, ge=0)


class BoardUpdate(BaseModel):
    rename_columns: list[RenameColumnAction] = Field(default_factory=list)
    create_cards: list[CreateCardAction] = Field(default_factory=list)
    update_cards: list[UpdateCardAction] = Field(default_factory=list)
    move_cards: list[MoveCardAction] = Field(default_factory=list)
    delete_cards: list[int] = Field(default_factory=list)


class StructuredAssistantResponse(BaseModel):
    assistant_response: str = Field(min_length=1)
    board_update: BoardUpdate | None = None


def _extract_json_string(raw_text: str) -> str:
    text = raw_text.strip()
    if text.startswith("```"):
        parts = text.split("```")
        for part in parts:
            candidate = part.strip()
            if candidate.startswith("json"):
                candidate = candidate[4:].strip()
            if candidate.startswith("{") and candidate.endswith("}"):
                return candidate
    if text.startswith("{") and text.endswith("}"):
        return text
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    return text


def parse_structured_response(raw_text: str) -> StructuredAssistantResponse:
    json_text = _extract_json_string(raw_text)
    try:
        payload: Any = json.loads(json_text)
    except json.JSONDecodeError as exc:
        raise ValueError("AI response was not valid JSON") from exc
    try:
        return StructuredAssistantResponse.model_validate(payload)
    except ValidationError as exc:
        raise ValueError("AI response did not match required schema") from exc


def build_ai_messages(
    board_payload: dict[str, Any],
    user_message: str,
    conversation_history: list[dict[str, str]],
) -> list[dict[str, str]]:
    messages: list[dict[str, str]] = [{"role": "system", "content": SYSTEM_PROMPT}]
    for item in conversation_history[-20:]:
        role = item.get("role")
        content = item.get("content")
        if role in {"user", "assistant"} and content:
            messages.append({"role": role, "content": content})
    messages.append(
        {
            "role": "user",
            "content": (
                "Current board JSON:\n"
                + json.dumps(board_payload, ensure_ascii=True)
                + "\n\nUser request:\n"
                + user_message
            ),
        }
    )
    return messages
