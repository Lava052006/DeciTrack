"""Interactive, read-only Wispr Flow integration check.

Run from the repository root with::

    python -m tests.manual.test_wispr_live

The existing OAuth flow may open a browser. This script never prints tokens or
credentials and only reads meeting data; it does not call persistence code.
"""

from __future__ import annotations

import asyncio
from typing import Any

from pydantic import ValidationError

from app.integrations.wispr.client import wispr_session
from app.integrations.wispr.normalizer import normalize_meeting
from app.integrations.wispr.service import (
    WisprMeetingService,
    WisprRetrievalError,
    WisprTranscriptUnavailable,
)
from app.schemas.ingestion import MeetingUpload


def _meeting_id(meeting: dict[str, Any]) -> str | None:
    value = meeting.get("id", meeting.get("meeting_id"))
    return value if isinstance(value, str) and value else None


def _meeting_title(meeting: dict[str, Any]) -> str:
    title = meeting.get("title")
    return title.strip() if isinstance(title, str) and title.strip() else "(untitled meeting)"


async def _choose_meeting(meetings: list[dict[str, Any]]) -> dict[str, Any] | None:
    if not meetings:
        print("Wispr returned no recent meetings.")
        return None

    selectable: list[dict[str, Any]] = []
    print("\nRecent Wispr meetings:")
    for meeting in meetings:
        meeting_id = _meeting_id(meeting)
        if meeting_id is None:
            continue
        selectable.append(meeting)
        print(f"{len(selectable)}. {_meeting_title(meeting)}  (ID: {meeting_id})")
    if not selectable:
        print("Wispr returned meetings without usable IDs.")
        return None

    while True:
        selection = input(f"Select a meeting number (1-{len(selectable)}), or q to quit: ").strip()
        if selection.lower() in {"q", "quit"}:
            return None
        try:
            index = int(selection)
        except ValueError:
            print("Enter a listed number or q.")
            continue
        if 1 <= index <= len(selectable):
            return selectable[index - 1]
        print(f"Enter a number from 1 to {len(selectable)}.")


def _display_result(normalized: Any) -> None:
    print("\nNormalized meeting metadata")
    print(f"  Source meeting ID: {normalized.source_meeting_id}")
    print(f"  Title: {normalized.upload.title}")
    print(f"  Date: {normalized.upload.meeting_date}")
    print(f"  Attendees: {', '.join(normalized.upload.attendees) or '(none supplied)'}")
    print(f"  Transcript segments: {len(normalized.segments)}")

    speakers = list(dict.fromkeys(segment.speaker for segment in normalized.segments if segment.speaker))
    print(f"  Speakers: {', '.join(speakers) or '(none identified)'}")
    print("\nTranscript segments (sequence, speaker, start time):")
    for segment in normalized.segments:
        speaker = segment.speaker if segment.speaker is not None else "(unknown)"
        timestamp = f"{segment.start_time:g}s" if segment.start_time is not None else "(unknown)"
        print(f"  {segment.sequence}: {speaker}, {timestamp}")

    preview = normalized.upload.transcript.strip()
    if len(preview) > 600:
        preview = preview[:600].rstrip() + "…"
    print("\nTranscript preview:")
    print(preview)


async def main() -> None:
    try:
        # Keep one authenticated MCP session for search and every transcript page.
        async with wispr_session() as session:
            service = WisprMeetingService(session=session)
            meetings = await service.search_meetings()
            print(f"Found {len(meetings)} recent meeting(s).")
            selected = await _choose_meeting(meetings)
            if selected is None:
                return

            source_id = _meeting_id(selected)
            if source_id is None:  # Defensive: the selection function requires this.
                print("Selected Wispr meeting has no usable ID.")
                return

            print(f"\nRetrieving complete transcript for {_meeting_title(selected)}…")
            try:
                fetched = await service.get_meeting(source_id)
            except WisprTranscriptUnavailable as exc:
                print(f"Transcript unavailable: {exc}")
                return

            normalized = normalize_meeting(fetched["meeting"], fetched["transcript"])
            # Validate exactly the established Phase 3 ingestion payload. This is
            # validation only; ingest_meeting and database code are never called.
            upload = MeetingUpload.model_validate(normalized.upload.model_dump())
            _display_result(normalized.model_copy(update={"upload": upload}))
            print("\nPhase 3 MeetingUpload schema validation: passed")
    except WisprRetrievalError as exc:
        print(f"Wispr retrieval failed: {exc}")
    except ValidationError as exc:
        print("Retrieved meeting could not be normalized to the Phase 3 ingestion schema:")
        print(exc)
    except (ValueError, TypeError) as exc:
        print(f"Meeting normalization failed: {exc}")
    except Exception as exc:
        # MCP/OAuth libraries may raise transport-specific exceptions. Do not
        # dump request headers or authentication state in this manual utility.
        print(f"Wispr connection or integration failed ({type(exc).__name__}).")


if __name__ == "__main__":
    asyncio.run(main())
