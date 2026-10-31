import re

from app.models.entities import TranscriptSegment

_TIMESTAMP = re.compile(r"^(?:\[(?P<bracket>[^\]]+)\]|(?P<plain>\d{1,2}:\d{2}(?::\d{2}(?:\.\d+)?)?|\d+(?:\.\d+)?))\s*(?:[-–|]\s*)?(?P<rest>.*)$")
_SPEAKER = re.compile(r"^(?P<speaker>[^:]{1,100}):\s*(?P<text>.*)$")


def _seconds(value: str) -> float | None:
    value = value.strip()
    if re.fullmatch(r"\d+(?:\.\d+)?", value):
        return float(value)
    parts = value.split(":")
    if len(parts) not in (2, 3):
        return None
    try:
        numbers = [float(part) for part in parts]
    except ValueError:
        return None
    if any(number < 0 for number in numbers) or any(number >= 60 for number in numbers[1:]):
        return None
    if len(numbers) == 2:
        return numbers[0] * 60 + numbers[1]
    return numbers[0] * 3600 + numbers[1] * 60 + numbers[2]


def parse_transcript(transcript: str, meeting_id: str) -> list[TranscriptSegment]:
    """Parse one transcript line per segment; absent metadata stays None."""
    segments: list[TranscriptSegment] = []
    for raw_line in transcript.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        timestamp = None
        match = _TIMESTAMP.match(line)
        if match:
            candidate = match.group("bracket") or match.group("plain")
            parsed = _seconds(candidate)
            if parsed is not None:
                timestamp = parsed
                line = match.group("rest").strip()
        speaker = None
        speaker_match = _SPEAKER.match(line)
        if speaker_match:
            speaker = speaker_match.group("speaker").strip() or None
            line = speaker_match.group("text").strip()
        if not line:
            continue
        segments.append(TranscriptSegment(
            meeting_id=meeting_id,
            speaker=speaker,
            start_time=timestamp,
            text=line,
            sequence=len(segments),
        ))
    if not segments:
        raise ValueError("transcript contains no usable text")
    return segments
