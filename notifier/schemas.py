"""Pydantic models for inbound webhook payloads.

GAS sends a JSON body shaped like:

    {
      "form_id": "1AbC...google-form-id",
      "submitted_at": "2026-06-02T22:00:00Z",
      "responses": [
        {"index": 0, "title": "Nama Lengkap", "answer": "Budi"},
        {"index": 1, "title": "NIP", "answer": "123456789012345678"},
        ...
      ]
    }

The receiver uses the responses list to build the Telegram message.
"""
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field, field_validator


class FormItemResponse(BaseModel):
    index: int = Field(..., ge=0)
    title: str = Field(..., min_length=1)
    answer: str = Field(default="")


class FormSubmitPayload(BaseModel):
    form_id: str = Field(..., min_length=1)
    submitted_at: datetime
    responses: list[FormItemResponse] = Field(..., min_length=1)
    chat_id: Optional[int] = None
    thread_id: Optional[int] = None

    @field_validator("responses")
    @classmethod
    def _responses_nonempty(cls, v: list[FormItemResponse]) -> list[FormItemResponse]:
        if not v:
            raise ValueError("responses must be non-empty")
        return v

    def find(self, title: str) -> Optional[str]:
        """Return the answer for a question whose title matches (case-insensitive),
        or None if not present."""
        t = title.strip().lower()
        for r in self.responses:
            if r.title.strip().lower() == t:
                return r.answer or None
        return None

    def format_message(self) -> str:
        """Build a multi-line text message from the responses.

        The format is intentionally simple. Future work could support
        a custom template via the webhook payload.
        """
        lines = ["Ada isian form baru\n"]
        for r in self.responses:
            lines.append(f"{r.title}: {r.answer}")
        return "\n".join(lines)
