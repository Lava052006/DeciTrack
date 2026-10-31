import json
from datetime import datetime, timezone
from uuid import UUID

import pytest
from pydantic import ValidationError

from app.models.entities import (
    ActionItem, ActionStatus, Approval, ApprovalStatus, Conflict, Decision,
    DecisionStatus, Meeting, MeetingStatus, TranscriptSegment, UnresolvedItem,
)


def test_meeting_defaults_and_json_serialization():
    meeting = Meeting(title="Planning")
    assert UUID(meeting.id)
    assert meeting.status == MeetingStatus.SCHEDULED
    assert meeting.created_at.tzinfo == timezone.utc
    payload = json.loads(meeting.model_dump_json())
    assert payload["id"] == meeting.id
    assert payload["status"] == "scheduled"


def test_optional_fields_default_to_none():
    segment = TranscriptSegment(meeting_id="meeting-1", text="Agreed", sequence=0)
    decision = Decision(meeting_id="meeting-1", summary="Ship it")
    action = ActionItem(meeting_id="meeting-1", title="Draft plan")
    assert segment.speaker is None and segment.start_time is None
    assert decision.owner_id is None
    assert action.owner_id is None and action.deadline is None


def test_all_entity_types_have_uuid_ids_and_timestamps():
    entities = [
        Meeting(title="Review"),
        TranscriptSegment(meeting_id="m1", text="Text", sequence=0),
        Decision(meeting_id="m1", summary="Choice"),
        ActionItem(meeting_id="m1", title="Task"),
        Conflict(meeting_id="m1", description="Mismatch"),
        UnresolvedItem(meeting_id="m1", description="Question"),
        Approval(meeting_id="m1", decision_id="d1"),
    ]
    for entity in entities:
        UUID(entity.id)
        assert isinstance(entity.created_at, datetime)
        assert isinstance(entity.updated_at, datetime)


@pytest.mark.parametrize("factory", [
    lambda: Meeting(title=""),
    lambda: Meeting(title="Review", status="unknown"),
    lambda: Decision(meeting_id="m1", summary="Choice", status="invalid"),
    lambda: ActionItem(meeting_id="m1", title="Task", deadline="not-a-date"),
    lambda: TranscriptSegment(meeting_id="m1", text="Text", sequence=-1),
    lambda: Meeting(id="not-a-uuid", title="Review"),
])
def test_invalid_values_are_rejected(factory):
    with pytest.raises(ValidationError):
        factory()


def test_status_enums_and_explicit_optionals():
    due = datetime(2026, 11, 1, tzinfo=timezone.utc)
    action = ActionItem(meeting_id="m1", title="Task", status=ActionStatus.IN_PROGRESS, deadline=due)
    approval = Approval(meeting_id="m1", decision_id="d1", status=ApprovalStatus.APPROVED)
    assert action.status == ActionStatus.IN_PROGRESS
    assert action.deadline == due
    assert approval.status == ApprovalStatus.APPROVED
