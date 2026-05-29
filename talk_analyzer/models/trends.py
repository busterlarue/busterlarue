"""
Trend analysis models for cross-talk insights.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum


class TrendDirection(Enum):
    """Direction of a trend."""
    IMPROVING = "improving"
    STABLE = "stable"
    DECLINING = "declining"
    FLUCTUATING = "fluctuating"


class ConnectionType(Enum):
    """Types of connections between talks."""
    THEMATIC = "thematic"       # Similar themes/topics
    SEQUENTIAL = "sequential"   # Follow-up or continuation
    CONTRASTING = "contrasting" # Different perspective on same topic
    REFERENCED = "referenced"   # Explicitly mentioned previous talk
    EVOLVED = "evolved"         # Same topic with evolved thinking


@dataclass
class TopicFrequency:
    """Tracks frequency of a topic across talks."""
    topic: str
    total_mentions: int = 0
    talks_mentioned_in: list[str] = field(default_factory=list)  # Talk IDs
    first_mentioned: Optional[datetime] = None
    last_mentioned: Optional[datetime] = None
    trend: TrendDirection = TrendDirection.STABLE

    @property
    def talk_count(self) -> int:
        """Number of unique talks mentioning this topic."""
        return len(set(self.talks_mentioned_in))

    def add_mention(self, talk_id: str, talk_date: datetime, count: int = 1):
        """Record a mention of this topic."""
        self.total_mentions += count
        if talk_id not in self.talks_mentioned_in:
            self.talks_mentioned_in.append(talk_id)
        if self.first_mentioned is None or talk_date < self.first_mentioned:
            self.first_mentioned = talk_date
        if self.last_mentioned is None or talk_date > self.last_mentioned:
            self.last_mentioned = talk_date


@dataclass
class DeliveryTrend:
    """Tracks a delivery metric over time."""
    metric_name: str  # e.g., "fillers_per_minute", "average_wpm"
    data_points: list[tuple[datetime, float]] = field(default_factory=list)
    direction: TrendDirection = TrendDirection.STABLE
    improvement_percentage: float = 0.0

    def add_data_point(self, date: datetime, value: float):
        """Add a data point to the trend."""
        self.data_points.append((date, value))
        self.data_points.sort(key=lambda x: x[0])
        self._recalculate_trend()

    def _recalculate_trend(self):
        """Recalculate trend direction and improvement."""
        if len(self.data_points) < 2:
            self.direction = TrendDirection.STABLE
            self.improvement_percentage = 0.0
            return

        # Simple linear trend analysis
        first_value = self.data_points[0][1]
        last_value = self.data_points[-1][1]

        if first_value == 0:
            self.improvement_percentage = 0.0
        else:
            self.improvement_percentage = ((last_value - first_value) / first_value) * 100

        # For metrics like fillers, lower is better
        is_lower_better = self.metric_name in ["fillers_per_minute", "filler_count", "rushed_segments"]

        if abs(self.improvement_percentage) < 5:
            self.direction = TrendDirection.STABLE
        elif is_lower_better:
            self.direction = TrendDirection.IMPROVING if self.improvement_percentage < 0 else TrendDirection.DECLINING
        else:
            self.direction = TrendDirection.IMPROVING if self.improvement_percentage > 0 else TrendDirection.DECLINING

    @property
    def average_value(self) -> float:
        """Calculate average value across all data points."""
        if not self.data_points:
            return 0.0
        return sum(v for _, v in self.data_points) / len(self.data_points)

    @property
    def latest_value(self) -> Optional[float]:
        """Get the most recent value."""
        if not self.data_points:
            return None
        return self.data_points[-1][1]


@dataclass
class TalkConnection:
    """A connection between two talks."""
    source_talk_id: str
    target_talk_id: str
    connection_type: ConnectionType
    strength: float = 0.0  # 0-1 similarity/connection strength
    shared_themes: list[str] = field(default_factory=list)
    shared_quotes: list[str] = field(default_factory=list)  # Quote IDs
    notes: str = ""

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "source_talk_id": self.source_talk_id,
            "target_talk_id": self.target_talk_id,
            "connection_type": self.connection_type.value,
            "strength": self.strength,
            "shared_themes": self.shared_themes,
            "shared_quotes": self.shared_quotes,
            "notes": self.notes,
        }


@dataclass
class RecurringInsight:
    """An insight or idea that recurs across multiple talks."""
    id: str
    core_idea: str
    variations: list[str] = field(default_factory=list)  # Different phrasings
    talk_ids: list[str] = field(default_factory=list)
    quote_ids: list[str] = field(default_factory=list)  # Related quotes
    evolution_notes: str = ""  # How this idea has evolved

    @property
    def occurrence_count(self) -> int:
        """Number of talks where this insight appears."""
        return len(set(self.talk_ids))


@dataclass
class AudiencePattern:
    """Patterns observed for different audience types."""
    audience_type: str
    talk_count: int = 0
    average_delivery_score: float = 0.0
    common_themes: list[str] = field(default_factory=list)
    best_performing_quotes: list[str] = field(default_factory=list)
    notes: str = ""


@dataclass
class TrendAnalysis:
    """
    Comprehensive trend analysis across multiple talks.
    """
    # Time range
    analysis_start: Optional[datetime] = None
    analysis_end: Optional[datetime] = None
    total_talks_analyzed: int = 0

    # Topic trends
    topic_frequencies: list[TopicFrequency] = field(default_factory=list)
    emerging_topics: list[str] = field(default_factory=list)  # Topics gaining frequency
    declining_topics: list[str] = field(default_factory=list)  # Topics losing frequency

    # Delivery trends
    delivery_trends: dict[str, DeliveryTrend] = field(default_factory=dict)

    # Cross-talk connections
    talk_connections: list[TalkConnection] = field(default_factory=list)
    recurring_insights: list[RecurringInsight] = field(default_factory=list)

    # Audience patterns
    audience_patterns: list[AudiencePattern] = field(default_factory=list)

    # Summary insights
    key_findings: list[str] = field(default_factory=list)
    recommendations: list[str] = field(default_factory=list)

    def get_topic_trend(self, topic: str) -> Optional[TopicFrequency]:
        """Get trend data for a specific topic."""
        for tf in self.topic_frequencies:
            if tf.topic.lower() == topic.lower():
                return tf
        return None

    def get_delivery_trend(self, metric: str) -> Optional[DeliveryTrend]:
        """Get trend data for a specific delivery metric."""
        return self.delivery_trends.get(metric)

    def get_connections_for_talk(self, talk_id: str) -> list[TalkConnection]:
        """Get all connections involving a specific talk."""
        return [c for c in self.talk_connections
                if c.source_talk_id == talk_id or c.target_talk_id == talk_id]

    def add_topic_mention(self, topic: str, talk_id: str, talk_date: datetime, count: int = 1):
        """Record a topic mention."""
        existing = self.get_topic_trend(topic)
        if existing:
            existing.add_mention(talk_id, talk_date, count)
        else:
            tf = TopicFrequency(topic=topic)
            tf.add_mention(talk_id, talk_date, count)
            self.topic_frequencies.append(tf)

    def add_delivery_data(self, metric: str, date: datetime, value: float):
        """Add a delivery metric data point."""
        if metric not in self.delivery_trends:
            self.delivery_trends[metric] = DeliveryTrend(metric_name=metric)
        self.delivery_trends[metric].add_data_point(date, value)

    @property
    def improving_metrics(self) -> list[str]:
        """Get list of metrics that are improving."""
        return [name for name, trend in self.delivery_trends.items()
                if trend.direction == TrendDirection.IMPROVING]

    @property
    def declining_metrics(self) -> list[str]:
        """Get list of metrics that are declining."""
        return [name for name, trend in self.delivery_trends.items()
                if trend.direction == TrendDirection.DECLINING]

    @property
    def top_topics(self) -> list[TopicFrequency]:
        """Get topics sorted by frequency."""
        return sorted(self.topic_frequencies,
                     key=lambda t: t.total_mentions,
                     reverse=True)[:10]

    def get_summary(self) -> dict:
        """Get a summary of trend analysis."""
        return {
            "total_talks": self.total_talks_analyzed,
            "date_range": {
                "start": self.analysis_start.isoformat() if self.analysis_start else None,
                "end": self.analysis_end.isoformat() if self.analysis_end else None,
            },
            "top_topics": [t.topic for t in self.top_topics[:5]],
            "improving_metrics": self.improving_metrics,
            "declining_metrics": self.declining_metrics,
            "total_connections": len(self.talk_connections),
            "recurring_insights_count": len(self.recurring_insights),
            "key_findings_count": len(self.key_findings),
        }

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "analysis_start": self.analysis_start.isoformat() if self.analysis_start else None,
            "analysis_end": self.analysis_end.isoformat() if self.analysis_end else None,
            "total_talks_analyzed": self.total_talks_analyzed,
            "topic_frequencies": [
                {
                    "topic": tf.topic,
                    "total_mentions": tf.total_mentions,
                    "talk_count": tf.talk_count,
                    "trend": tf.trend.value,
                }
                for tf in self.topic_frequencies
            ],
            "emerging_topics": self.emerging_topics,
            "declining_topics": self.declining_topics,
            "delivery_trends": {
                name: {
                    "direction": trend.direction.value,
                    "improvement_percentage": trend.improvement_percentage,
                    "average_value": trend.average_value,
                    "latest_value": trend.latest_value,
                    "data_point_count": len(trend.data_points),
                }
                for name, trend in self.delivery_trends.items()
            },
            "talk_connections": [c.to_dict() for c in self.talk_connections],
            "recurring_insights": [
                {
                    "id": ri.id,
                    "core_idea": ri.core_idea,
                    "occurrence_count": ri.occurrence_count,
                }
                for ri in self.recurring_insights
            ],
            "key_findings": self.key_findings,
            "recommendations": self.recommendations,
        }
