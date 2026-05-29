"""
Delivery metrics models for speech analysis.
"""

from dataclasses import dataclass, field
from typing import Optional
from enum import Enum


class PacingLevel(Enum):
    """Pacing assessment levels."""
    VERY_SLOW = "very_slow"
    SLOW = "slow"
    OPTIMAL = "optimal"
    FAST = "fast"
    RUSHED = "rushed"


class EnergyLevel(Enum):
    """Energy level indicators."""
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    PEAK = "peak"


class ToneType(Enum):
    """Types of tonal shifts detected."""
    NEUTRAL = "neutral"
    ENTHUSIASTIC = "enthusiastic"
    SERIOUS = "serious"
    HUMOROUS = "humorous"
    EMPHATIC = "emphatic"
    REFLECTIVE = "reflective"
    QUESTIONING = "questioning"


@dataclass
class FillerInstance:
    """A single instance of a filler word."""
    word: str
    position: int  # Character position in transcript
    timestamp: Optional[float] = None  # Seconds from start
    context: str = ""  # Surrounding text for context

    @property
    def timestamp_formatted(self) -> str:
        """Return timestamp in MM:SS format."""
        if self.timestamp is None:
            return ""
        minutes, seconds = divmod(int(self.timestamp), 60)
        return f"{minutes}:{seconds:02d}"


@dataclass
class FillerAnalysis:
    """Analysis of filler words in a talk."""
    total_count: int = 0
    filler_instances: list[FillerInstance] = field(default_factory=list)
    filler_counts: dict[str, int] = field(default_factory=dict)
    fillers_per_minute: float = 0.0

    @property
    def most_common_filler(self) -> Optional[str]:
        """Return the most frequently used filler word."""
        if not self.filler_counts:
            return None
        return max(self.filler_counts, key=self.filler_counts.get)

    @property
    def assessment(self) -> str:
        """Provide an assessment of filler word usage."""
        if self.fillers_per_minute < 1:
            return "Excellent - minimal filler usage"
        elif self.fillers_per_minute < 2:
            return "Good - occasional fillers"
        elif self.fillers_per_minute < 4:
            return "Moderate - noticeable filler usage"
        elif self.fillers_per_minute < 6:
            return "High - frequent fillers affecting flow"
        else:
            return "Very High - fillers significantly impacting delivery"

    def get_hotspots(self, window_seconds: float = 60) -> list[tuple[float, int]]:
        """Find time windows with highest filler concentration."""
        if not self.filler_instances or not any(f.timestamp for f in self.filler_instances):
            return []

        timestamped = [f for f in self.filler_instances if f.timestamp is not None]
        if not timestamped:
            return []

        timestamped.sort(key=lambda x: x.timestamp)

        # Sliding window analysis
        hotspots = []
        i = 0
        while i < len(timestamped):
            window_start = timestamped[i].timestamp
            window_end = window_start + window_seconds
            count = sum(1 for f in timestamped if window_start <= f.timestamp < window_end)
            if count >= 3:  # Threshold for a "hotspot"
                hotspots.append((window_start, count))
            i += 1

        return hotspots


@dataclass
class PauseInstance:
    """A detected pause in speech."""
    start_time: float
    end_time: float
    preceding_text: str = ""
    following_text: str = ""

    @property
    def duration(self) -> float:
        """Duration of the pause in seconds."""
        return self.end_time - self.start_time

    @property
    def timestamp_formatted(self) -> str:
        """Return start time in MM:SS format."""
        minutes, seconds = divmod(int(self.start_time), 60)
        return f"{minutes}:{seconds:02d}"

    @property
    def is_dramatic(self) -> bool:
        """Check if this is a dramatic pause (4+ seconds)."""
        return self.duration >= 4.0

    @property
    def is_significant(self) -> bool:
        """Check if this is a significant pause (2+ seconds)."""
        return self.duration >= 2.0


@dataclass
class PauseAnalysis:
    """Analysis of pauses in a talk."""
    pauses: list[PauseInstance] = field(default_factory=list)
    total_pause_time: float = 0.0
    average_pause_duration: float = 0.0

    @property
    def significant_pauses(self) -> list[PauseInstance]:
        """Get pauses that are 2+ seconds."""
        return [p for p in self.pauses if p.is_significant]

    @property
    def dramatic_pauses(self) -> list[PauseInstance]:
        """Get pauses that are 4+ seconds."""
        return [p for p in self.pauses if p.is_dramatic]


@dataclass
class PacingSegment:
    """Pacing analysis for a segment of the talk."""
    segment_index: int
    start_time: float
    end_time: float
    words_per_minute: float
    level: PacingLevel
    word_count: int

    @property
    def timestamp_formatted(self) -> str:
        """Return start time in MM:SS format."""
        minutes, seconds = divmod(int(self.start_time), 60)
        return f"{minutes}:{seconds:02d}"


@dataclass
class PacingAnalysis:
    """Overall pacing analysis for a talk."""
    average_wpm: float = 0.0
    segments: list[PacingSegment] = field(default_factory=list)
    overall_level: PacingLevel = PacingLevel.OPTIMAL

    @property
    def rushed_segments(self) -> list[PacingSegment]:
        """Get segments where speaker was rushing."""
        return [s for s in self.segments if s.level in (PacingLevel.FAST, PacingLevel.RUSHED)]

    @property
    def slow_segments(self) -> list[PacingSegment]:
        """Get segments where speaker was slow."""
        return [s for s in self.segments if s.level in (PacingLevel.SLOW, PacingLevel.VERY_SLOW)]

    @property
    def optimal_segments(self) -> list[PacingSegment]:
        """Get segments with optimal pacing."""
        return [s for s in self.segments if s.level == PacingLevel.OPTIMAL]

    @property
    def consistency_score(self) -> float:
        """Calculate pacing consistency (0-100). Higher is more consistent."""
        if len(self.segments) < 2:
            return 100.0

        wpms = [s.words_per_minute for s in self.segments]
        avg = sum(wpms) / len(wpms)
        if avg == 0:
            return 100.0

        variance = sum((wpm - avg) ** 2 for wpm in wpms) / len(wpms)
        std_dev = variance ** 0.5

        # Convert to 0-100 score (lower variance = higher score)
        # A std_dev of 30 WPM gives score of 70, std_dev of 0 gives 100
        score = max(0, 100 - (std_dev * 1.0))
        return round(score, 1)


@dataclass
class EnergyPoint:
    """Energy level at a point in time."""
    timestamp: float
    level: EnergyLevel
    context: str = ""  # What was being discussed
    indicators: list[str] = field(default_factory=list)  # What indicated this energy level

    @property
    def timestamp_formatted(self) -> str:
        """Return timestamp in MM:SS format."""
        minutes, seconds = divmod(int(self.timestamp), 60)
        return f"{minutes}:{seconds:02d}"


@dataclass
class EnergyAnalysis:
    """Energy level analysis throughout a talk."""
    energy_timeline: list[EnergyPoint] = field(default_factory=list)
    average_level: EnergyLevel = EnergyLevel.MODERATE
    peak_moments: list[EnergyPoint] = field(default_factory=list)
    low_moments: list[EnergyPoint] = field(default_factory=list)

    @property
    def energy_variation_score(self) -> float:
        """Score for energy variation (0-100). Some variation is good."""
        if len(self.energy_timeline) < 3:
            return 50.0

        levels = [e.level for e in self.energy_timeline]
        unique_levels = set(levels)

        # Score based on variety
        if len(unique_levels) == 1:
            return 30.0  # Monotone
        elif len(unique_levels) == 2:
            return 60.0  # Some variation
        elif len(unique_levels) == 3:
            return 85.0  # Good variation
        else:
            return 100.0  # Full range


@dataclass
class ToneShift:
    """A detected shift in tone."""
    timestamp: float
    from_tone: ToneType
    to_tone: ToneType
    context: str = ""

    @property
    def timestamp_formatted(self) -> str:
        """Return timestamp in MM:SS format."""
        minutes, seconds = divmod(int(self.timestamp), 60)
        return f"{minutes}:{seconds:02d}"


@dataclass
class DeliveryMetrics:
    """
    Complete delivery metrics for a talk.
    Aggregates all speech analysis components.
    """
    talk_id: str
    filler_analysis: FillerAnalysis = field(default_factory=FillerAnalysis)
    pacing_analysis: PacingAnalysis = field(default_factory=PacingAnalysis)
    pause_analysis: PauseAnalysis = field(default_factory=PauseAnalysis)
    energy_analysis: EnergyAnalysis = field(default_factory=EnergyAnalysis)
    tone_shifts: list[ToneShift] = field(default_factory=list)

    @property
    def overall_delivery_score(self) -> float:
        """
        Calculate an overall delivery score (0-100).
        Weighs different components of delivery.
        """
        scores = []

        # Filler score (lower is better)
        filler_score = max(0, 100 - (self.filler_analysis.fillers_per_minute * 15))
        scores.append(filler_score * 0.25)

        # Pacing consistency score
        scores.append(self.pacing_analysis.consistency_score * 0.25)

        # Energy variation score
        scores.append(self.energy_analysis.energy_variation_score * 0.25)

        # Optimal pacing percentage
        total_segments = len(self.pacing_analysis.segments)
        if total_segments > 0:
            optimal_pct = len(self.pacing_analysis.optimal_segments) / total_segments * 100
            scores.append(optimal_pct * 0.25)
        else:
            scores.append(50 * 0.25)

        return round(sum(scores), 1)

    def get_summary(self) -> dict:
        """Get a summary of delivery metrics."""
        return {
            "overall_score": self.overall_delivery_score,
            "filler_count": self.filler_analysis.total_count,
            "fillers_per_minute": round(self.filler_analysis.fillers_per_minute, 2),
            "average_wpm": round(self.pacing_analysis.average_wpm, 1),
            "pacing_consistency": self.pacing_analysis.consistency_score,
            "rushed_segments": len(self.pacing_analysis.rushed_segments),
            "slow_segments": len(self.pacing_analysis.slow_segments),
            "significant_pauses": len(self.pause_analysis.significant_pauses),
            "tone_shifts": len(self.tone_shifts),
        }

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "talk_id": self.talk_id,
            "overall_score": self.overall_delivery_score,
            "filler_analysis": {
                "total_count": self.filler_analysis.total_count,
                "filler_counts": self.filler_analysis.filler_counts,
                "fillers_per_minute": self.filler_analysis.fillers_per_minute,
                "instances": [
                    {
                        "word": f.word,
                        "position": f.position,
                        "timestamp": f.timestamp,
                        "context": f.context,
                    }
                    for f in self.filler_analysis.filler_instances
                ],
            },
            "pacing_analysis": {
                "average_wpm": self.pacing_analysis.average_wpm,
                "overall_level": self.pacing_analysis.overall_level.value,
                "consistency_score": self.pacing_analysis.consistency_score,
                "segments": [
                    {
                        "segment_index": s.segment_index,
                        "start_time": s.start_time,
                        "end_time": s.end_time,
                        "words_per_minute": s.words_per_minute,
                        "level": s.level.value,
                    }
                    for s in self.pacing_analysis.segments
                ],
            },
            "pause_analysis": {
                "total_pause_time": self.pause_analysis.total_pause_time,
                "average_duration": self.pause_analysis.average_pause_duration,
                "significant_count": len(self.pause_analysis.significant_pauses),
                "pauses": [
                    {
                        "start_time": p.start_time,
                        "end_time": p.end_time,
                        "duration": p.duration,
                        "preceding_text": p.preceding_text,
                        "following_text": p.following_text,
                    }
                    for p in self.pause_analysis.pauses
                ],
            },
            "energy_analysis": {
                "average_level": self.energy_analysis.average_level.value,
                "variation_score": self.energy_analysis.energy_variation_score,
                "peak_count": len(self.energy_analysis.peak_moments),
                "low_count": len(self.energy_analysis.low_moments),
            },
            "tone_shifts": [
                {
                    "timestamp": t.timestamp,
                    "from_tone": t.from_tone.value,
                    "to_tone": t.to_tone.value,
                    "context": t.context,
                }
                for t in self.tone_shifts
            ],
        }
