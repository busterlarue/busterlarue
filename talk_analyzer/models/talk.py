"""
Core Talk model and related data structures.
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
from enum import Enum
import uuid


class AudienceType(Enum):
    """Types of audiences for talks."""
    CORPORATE = "corporate"
    ACADEMIC = "academic"
    GENERAL_PUBLIC = "general_public"
    TECHNICAL = "technical"
    EXECUTIVE = "executive"
    WORKSHOP = "workshop"
    PODCAST = "podcast"
    WEBINAR = "webinar"
    CONFERENCE = "conference"
    OTHER = "other"


@dataclass
class TalkMetadata:
    """Metadata about a talk."""
    title: str
    date: datetime
    venue: Optional[str] = None
    topic: Optional[str] = None
    audience_type: AudienceType = AudienceType.OTHER
    audience_size: Optional[int] = None
    duration_seconds: Optional[float] = None
    tags: list[str] = field(default_factory=list)
    notes: Optional[str] = None

    @property
    def duration(self) -> Optional[timedelta]:
        """Return duration as timedelta."""
        if self.duration_seconds:
            return timedelta(seconds=self.duration_seconds)
        return None

    @property
    def duration_formatted(self) -> str:
        """Return duration in HH:MM:SS format."""
        if not self.duration_seconds:
            return "Unknown"
        hours, remainder = divmod(int(self.duration_seconds), 3600)
        minutes, seconds = divmod(remainder, 60)
        if hours:
            return f"{hours}:{minutes:02d}:{seconds:02d}"
        return f"{minutes}:{seconds:02d}"


@dataclass
class Segment:
    """A timed segment of the transcript."""
    text: str
    start_time: Optional[float] = None  # Seconds from start
    end_time: Optional[float] = None    # Seconds from start
    segment_index: int = 0
    word_count: int = field(init=False)

    def __post_init__(self):
        self.word_count = len(self.text.split())

    @property
    def duration(self) -> Optional[float]:
        """Duration of segment in seconds."""
        if self.start_time is not None and self.end_time is not None:
            return self.end_time - self.start_time
        return None

    @property
    def words_per_minute(self) -> Optional[float]:
        """Calculate words per minute for this segment."""
        duration = self.duration
        if duration and duration > 0:
            return (self.word_count / duration) * 60
        return None

    @property
    def timestamp_formatted(self) -> str:
        """Return start time in MM:SS format."""
        if self.start_time is None:
            return ""
        minutes, seconds = divmod(int(self.start_time), 60)
        return f"{minutes}:{seconds:02d}"


@dataclass
class Talk:
    """
    The core Talk entity representing a single recorded talk/presentation.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    metadata: TalkMetadata = field(default_factory=lambda: TalkMetadata(
        title="Untitled Talk",
        date=datetime.now()
    ))
    raw_transcript: str = ""
    segments: list[Segment] = field(default_factory=list)
    created_at: datetime = field(default_factory=datetime.now)
    updated_at: datetime = field(default_factory=datetime.now)

    @property
    def word_count(self) -> int:
        """Total word count of the talk."""
        return len(self.raw_transcript.split())

    @property
    def full_text(self) -> str:
        """Return the full transcript text."""
        if self.segments:
            return " ".join(seg.text for seg in self.segments)
        return self.raw_transcript

    def get_segment_at_time(self, time_seconds: float) -> Optional[Segment]:
        """Find the segment that contains the given timestamp."""
        for segment in self.segments:
            if segment.start_time is None or segment.end_time is None:
                continue
            if segment.start_time <= time_seconds <= segment.end_time:
                return segment
        return None

    def get_text_around_time(self, time_seconds: float, context_seconds: float = 30) -> str:
        """Get transcript text around a specific timestamp."""
        relevant_segments = []
        for segment in self.segments:
            if segment.start_time is None or segment.end_time is None:
                continue
            # Check if segment overlaps with our time window
            window_start = time_seconds - context_seconds
            window_end = time_seconds + context_seconds
            if segment.end_time >= window_start and segment.start_time <= window_end:
                relevant_segments.append(segment)
        return " ".join(seg.text for seg in relevant_segments)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "metadata": {
                "title": self.metadata.title,
                "date": self.metadata.date.isoformat(),
                "venue": self.metadata.venue,
                "topic": self.metadata.topic,
                "audience_type": self.metadata.audience_type.value,
                "audience_size": self.metadata.audience_size,
                "duration_seconds": self.metadata.duration_seconds,
                "tags": self.metadata.tags,
                "notes": self.metadata.notes,
            },
            "raw_transcript": self.raw_transcript,
            "segments": [
                {
                    "text": seg.text,
                    "start_time": seg.start_time,
                    "end_time": seg.end_time,
                    "segment_index": seg.segment_index,
                }
                for seg in self.segments
            ],
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Talk":
        """Create Talk from dictionary."""
        metadata = TalkMetadata(
            title=data["metadata"]["title"],
            date=datetime.fromisoformat(data["metadata"]["date"]),
            venue=data["metadata"].get("venue"),
            topic=data["metadata"].get("topic"),
            audience_type=AudienceType(data["metadata"].get("audience_type", "other")),
            audience_size=data["metadata"].get("audience_size"),
            duration_seconds=data["metadata"].get("duration_seconds"),
            tags=data["metadata"].get("tags", []),
            notes=data["metadata"].get("notes"),
        )
        segments = [
            Segment(
                text=seg["text"],
                start_time=seg.get("start_time"),
                end_time=seg.get("end_time"),
                segment_index=seg.get("segment_index", i),
            )
            for i, seg in enumerate(data.get("segments", []))
        ]
        return cls(
            id=data["id"],
            metadata=metadata,
            raw_transcript=data.get("raw_transcript", ""),
            segments=segments,
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )
