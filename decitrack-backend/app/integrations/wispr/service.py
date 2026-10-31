"""Read meetings and complete transcript ranges from Wispr Flow over MCP."""

from __future__ import annotations

import json
import re
from typing import Any

from app.integrations.wispr.client import wispr_session


class WisprRetrievalError(RuntimeError):
    """Wispr returned an unusable response or an MCP request failed."""


class WisprMeetingNotFound(WisprRetrievalError):
    pass


class WisprTranscriptUnavailable(WisprRetrievalError):
    pass


class WisprTruncatedTranscript(WisprRetrievalError):
    pass


def _payload(result: Any) -> dict[str, Any]:
    if getattr(result, "isError", False) or (isinstance(result, dict) and result.get("isError")):
        raise WisprRetrievalError("Wispr MCP returned an error")
    structured = getattr(result, "structuredContent", None)
    if isinstance(structured, dict):
        return structured
    content = getattr(result, "content", None)
    if isinstance(content, list):
        for item in content:
            text = getattr(item, "text", None)
            if isinstance(text, str):
                try:
                    value = json.loads(text)
                except json.JSONDecodeError:
                    continue
                if isinstance(value, dict):
                    return value
    if isinstance(result, dict):
        if isinstance(result.get("result"), dict):
            return result["result"]
        return result
    raise WisprRetrievalError("Wispr MCP returned a malformed response")


def _truncated(data: dict[str, Any]) -> tuple[bool, Any]:
    transcript = data.get("transcript")
    candidates = [transcript, data]
    for candidate in candidates:
        if isinstance(candidate, dict):
            for key in ("next_offset", "continuation_offset", "next_start_char"):
                if candidate.get(key) is not None:
                    return True, candidate[key]
            if candidate.get("truncated") is True or candidate.get("has_more") is True:
                return True, None
    return False, None


class WisprMeetingService:
    """Thin async facade; accepts an MCP session for deterministic tests."""

    def __init__(self, session: Any | None = None):
        self._session = session

    async def _call(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        try:
            if self._session is None:
                async with wispr_session() as session:
                    result = await session.call_tool(name, arguments)
            else:
                result = await self._session.call_tool(name, arguments)
            return _payload(result)
        except WisprRetrievalError:
            raise
        except Exception as exc:
            raise WisprRetrievalError(f"Wispr MCP call {name} failed") from exc

    async def search_meetings(self, query: str | None = None, **filters: Any) -> list[dict[str, Any]]:
        """Return every search result, forwarding opaque Wispr cursors verbatim."""
        args = dict(filters)
        if query is not None:
            args["query"] = query
        meetings: list[dict[str, Any]] = []
        seen_cursors: set[str] = set()
        while True:
            data = await self._call("search_meetings", args)
            page = data.get("meetings", data.get("results"))
            if not isinstance(page, list) or any(not isinstance(item, dict) for item in page):
                raise WisprRetrievalError("Wispr search response has malformed meetings")
            meetings.extend(page)
            if data.get("truncated") is True:
                raise WisprTruncatedTranscript("Wispr search exceeded its result cap")
            if data.get("has_more") is not True:
                return meetings
            cursor = data.get("next_cursor")
            if cursor is None:
                raise WisprRetrievalError("Wispr search omitted its continuation cursor")
            key = json.dumps(cursor, sort_keys=True)
            if key in seen_cursors:
                raise WisprRetrievalError("Wispr search repeated a continuation cursor")
            seen_cursors.add(key)
            args["cursor"] = cursor

    async def get_meeting(self, meeting_id: str) -> dict[str, Any]:
        """Fetch meeting metadata and all transcript pages with explicit opt-in."""
        if not isinstance(meeting_id, str) or not meeting_id.strip():
            raise ValueError("meeting_id must be a non-empty string")
        data = await self._call("get_meeting", {"meeting_id": meeting_id, "view_transcript": {}})
        if data.get("found") is False or data.get("meeting") is None and data.get("id") is None:
            raise WisprMeetingNotFound(f"Wispr meeting {meeting_id!r} was not found")
        meeting = data.get("meeting", data)
        if not isinstance(meeting, dict):
            raise WisprRetrievalError("Wispr meeting response is malformed")
        transcript = data.get("transcript", meeting.get("transcript"))
        if isinstance(transcript, dict):
            text = transcript.get("text", transcript.get("content"))
        else:
            text = transcript
        if not isinstance(text, str) or not text.strip():
            raise WisprTranscriptUnavailable("Wispr meeting has no transcript")
        truncated, offset = _truncated(data)
        if truncated:
            # Do not infer or adjust this offset; Wispr defines its exact range.
            if offset is None:
                marker = re.search(r"(?:continuation|next)[^\d]*(\d+)", text, re.IGNORECASE)
                offset = marker.group(1) if marker else None
            if offset is None:
                raise WisprTruncatedTranscript("Wispr transcript is truncated without an offset")
            while True:
                page = await self._call("get_meeting", {
                    "meeting_id": meeting_id,
                    "view_transcript": {"start_char": offset},
                })
                next_transcript = page.get("transcript")
                if isinstance(next_transcript, dict):
                    next_text = next_transcript.get("text", next_transcript.get("content"))
                else:
                    next_text = next_transcript
                if not isinstance(next_text, str):
                    raise WisprRetrievalError("Wispr transcript continuation is malformed")
                # A range starts at the exact server offset; the service concatenates
                # ranges in the received order and leaves their contents untouched.
                text += next_text
                more, next_offset = _truncated(page)
                if not more:
                    break
                if next_offset is None or next_offset == offset:
                    raise WisprTruncatedTranscript("Wispr transcript continuation did not advance")
                offset = next_offset
        return {"meeting": meeting, "transcript": text}
