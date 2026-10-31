from types import SimpleNamespace

import pytest

from app.integrations.wispr.normalizer import normalize_meeting
from app.integrations.wispr.service import (
    WisprMeetingNotFound,
    WisprMeetingService,
    WisprRetrievalError,
    WisprTranscriptUnavailable,
)


class FakeSession:
    def __init__(self, responses):
        self.responses = list(responses)
        self.calls = []

    async def call_tool(self, name, arguments):
        self.calls.append((name, arguments))
        result = self.responses.pop(0)
        if isinstance(result, Exception):
            raise result
        return SimpleNamespace(structuredContent=result, isError=False)


@pytest.mark.asyncio
async def test_search_paginates_with_exact_cursor_and_retrieves_meeting():
    search_session = FakeSession([
        {"meetings": [{"id": "m1"}], "has_more": True, "next_cursor": "opaque:7"},
        {"meetings": [{"id": "m2"}], "has_more": False},
    ])
    service = WisprMeetingService(search_session)
    assert await service.search_meetings("review") == [{"id": "m1"}, {"id": "m2"}]
    assert search_session.calls[1][1]["cursor"] == "opaque:7"

    session = FakeSession([{"meeting": {"id": "m1"}, "transcript": "[00:01] Ada: Hi"}])
    result = await WisprMeetingService(session).get_meeting("m1")
    assert result["transcript"] == "[00:01] Ada: Hi"
    assert session.calls == [("get_meeting", {"meeting_id": "m1", "view_transcript": {}})]


@pytest.mark.asyncio
async def test_missing_meeting_and_transcript_are_reported():
    with pytest.raises(WisprMeetingNotFound):
        await WisprMeetingService(FakeSession([{"found": False}])).get_meeting("gone")
    with pytest.raises(WisprTranscriptUnavailable):
        await WisprMeetingService(FakeSession([{"meeting": {"id": "m"}, "transcript": " "}])).get_meeting("m")


@pytest.mark.asyncio
async def test_transcript_paginates_using_exact_continuation_offset():
    session = FakeSession([
        {"meeting": {"id": "m"}, "transcript": {"text": "[00:01] Ada: Hel", "truncated": True, "next_offset": 17}},
        {"transcript": {"text": "lo", "truncated": False}},
    ])
    result = await WisprMeetingService(session).get_meeting("m")
    assert result["transcript"] == "[00:01] Ada: Hello"
    assert session.calls[1][1]["view_transcript"] == {"start_char": 17}


def test_normalizer_preserves_order_timestamp_speaker_and_source_id():
    normalized = normalize_meeting(
        {"id": "wispr-42", "title": "Planning", "start_time": "2026-10-30T12:30:00Z",
         "attendees": [{"name": "Ada"}]},
        "[00:01:02.5] Ada: First\nUnattributed second",
    )
    assert normalized.source_meeting_id == "wispr-42"
    assert normalized.upload.meeting_date.isoformat() == "2026-10-30T12:30:00+00:00"
    assert [(s.sequence, s.speaker, s.start_time, s.text) for s in normalized.segments] == [
        (0, "Ada", 62.5, "First"), (1, None, None, "Unattributed second")
    ]
    assert normalized.segments[0].meeting_id == "wispr-42"


@pytest.mark.asyncio
async def test_malformed_responses_and_mcp_failures_raise_domain_error():
    with pytest.raises(WisprRetrievalError):
        await WisprMeetingService(FakeSession([{"meetings": "not a list"}])).search_meetings()
    with pytest.raises(WisprRetrievalError):
        await WisprMeetingService(FakeSession([RuntimeError("offline")])).search_meetings()
    error = SimpleNamespace(structuredContent={"error": "denied"}, isError=True)
    with pytest.raises(WisprRetrievalError):
        await WisprMeetingService(FakeSession([error])).search_meetings()
