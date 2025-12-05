"""
Quote extraction and management models.
"""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional
from enum import Enum
import uuid


class QuoteCategory(Enum):
    """Categories for extracted quotes."""
    INSPIRING = "inspiring"
    INSIGHTFUL = "insightful"
    PRACTICAL = "practical"
    HUMOROUS = "humorous"
    PROVOCATIVE = "provocative"
    MEMORABLE = "memorable"
    QUOTABLE = "quotable"  # Generic "this is quotable"
    STORY = "story"        # Anecdote or story snippet
    STATISTIC = "statistic"  # Data-driven statement
    CALL_TO_ACTION = "call_to_action"


class QuoteQuality(Enum):
    """Quality rating for quotes."""
    OUTSTANDING = "outstanding"  # Top tier, marketing-ready
    EXCELLENT = "excellent"      # Very good, reusable
    GOOD = "good"               # Solid, contextually useful
    FAIR = "fair"               # Needs refinement


@dataclass
class Quote:
    """
    An extracted quote or snippet from a talk.
    """
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    text: str = ""
    talk_id: str = ""

    # Context and timing
    timestamp: Optional[float] = None  # Seconds from start
    context_before: str = ""           # What came before
    context_after: str = ""            # What came after
    topic_context: str = ""            # What topic was being discussed

    # Classification
    categories: list[QuoteCategory] = field(default_factory=list)
    quality: QuoteQuality = QuoteQuality.GOOD
    tags: list[str] = field(default_factory=list)

    # Usage tracking
    reuse_count: int = 0
    last_used: Optional[datetime] = None
    used_in_talks: list[str] = field(default_factory=list)  # Talk IDs where reused
    used_in_content: list[str] = field(default_factory=list)  # Content pieces using this

    # Metadata
    created_at: datetime = field(default_factory=datetime.now)
    notes: str = ""
    is_favorite: bool = False

    @property
    def word_count(self) -> int:
        """Number of words in the quote."""
        return len(self.text.split())

    @property
    def timestamp_formatted(self) -> str:
        """Return timestamp in MM:SS format."""
        if self.timestamp is None:
            return ""
        minutes, seconds = divmod(int(self.timestamp), 60)
        return f"{minutes}:{seconds:02d}"

    @property
    def category_labels(self) -> list[str]:
        """Get human-readable category labels."""
        return [cat.value.replace("_", " ").title() for cat in self.categories]

    @property
    def hashtags(self) -> str:
        """Get categories and tags as hashtags."""
        all_tags = [f"#{cat.value}" for cat in self.categories] + [f"#{tag}" for tag in self.tags]
        return " ".join(all_tags)

    def mark_used(self, context: str = "", talk_id: Optional[str] = None):
        """Mark this quote as used."""
        self.reuse_count += 1
        self.last_used = datetime.now()
        if talk_id and talk_id not in self.used_in_talks:
            self.used_in_talks.append(talk_id)
        if context and context not in self.used_in_content:
            self.used_in_content.append(context)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "id": self.id,
            "text": self.text,
            "talk_id": self.talk_id,
            "timestamp": self.timestamp,
            "context_before": self.context_before,
            "context_after": self.context_after,
            "topic_context": self.topic_context,
            "categories": [c.value for c in self.categories],
            "quality": self.quality.value,
            "tags": self.tags,
            "reuse_count": self.reuse_count,
            "last_used": self.last_used.isoformat() if self.last_used else None,
            "used_in_talks": self.used_in_talks,
            "used_in_content": self.used_in_content,
            "created_at": self.created_at.isoformat(),
            "notes": self.notes,
            "is_favorite": self.is_favorite,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Quote":
        """Create Quote from dictionary."""
        return cls(
            id=data["id"],
            text=data["text"],
            talk_id=data["talk_id"],
            timestamp=data.get("timestamp"),
            context_before=data.get("context_before", ""),
            context_after=data.get("context_after", ""),
            topic_context=data.get("topic_context", ""),
            categories=[QuoteCategory(c) for c in data.get("categories", [])],
            quality=QuoteQuality(data.get("quality", "good")),
            tags=data.get("tags", []),
            reuse_count=data.get("reuse_count", 0),
            last_used=datetime.fromisoformat(data["last_used"]) if data.get("last_used") else None,
            used_in_talks=data.get("used_in_talks", []),
            used_in_content=data.get("used_in_content", []),
            created_at=datetime.fromisoformat(data["created_at"]) if data.get("created_at") else datetime.now(),
            notes=data.get("notes", ""),
            is_favorite=data.get("is_favorite", False),
        )


@dataclass
class QuoteCollection:
    """
    A collection of quotes with search and filter capabilities.
    """
    quotes: list[Quote] = field(default_factory=list)

    def add(self, quote: Quote):
        """Add a quote to the collection."""
        self.quotes.append(quote)

    def get_by_id(self, quote_id: str) -> Optional[Quote]:
        """Get a quote by its ID."""
        for quote in self.quotes:
            if quote.id == quote_id:
                return quote
        return None

    def get_by_talk(self, talk_id: str) -> list[Quote]:
        """Get all quotes from a specific talk."""
        return [q for q in self.quotes if q.talk_id == talk_id]

    def get_by_category(self, category: QuoteCategory) -> list[Quote]:
        """Get quotes with a specific category."""
        return [q for q in self.quotes if category in q.categories]

    def get_by_quality(self, min_quality: QuoteQuality) -> list[Quote]:
        """Get quotes at or above a quality level."""
        quality_order = [
            QuoteQuality.FAIR,
            QuoteQuality.GOOD,
            QuoteQuality.EXCELLENT,
            QuoteQuality.OUTSTANDING,
        ]
        min_index = quality_order.index(min_quality)
        return [q for q in self.quotes if quality_order.index(q.quality) >= min_index]

    def get_favorites(self) -> list[Quote]:
        """Get all favorited quotes."""
        return [q for q in self.quotes if q.is_favorite]

    def get_most_reused(self, limit: int = 10) -> list[Quote]:
        """Get the most frequently reused quotes."""
        sorted_quotes = sorted(self.quotes, key=lambda q: q.reuse_count, reverse=True)
        return sorted_quotes[:limit]

    def get_unused(self) -> list[Quote]:
        """Get quotes that haven't been reused yet."""
        return [q for q in self.quotes if q.reuse_count == 0]

    def search(self, query: str) -> list[Quote]:
        """Search quotes by text content."""
        query_lower = query.lower()
        return [q for q in self.quotes if query_lower in q.text.lower()]

    def filter_by_tags(self, tags: list[str]) -> list[Quote]:
        """Get quotes that have any of the specified tags."""
        return [q for q in self.quotes if any(tag in q.tags for tag in tags)]

    @property
    def outstanding_quotes(self) -> list[Quote]:
        """Get all outstanding quality quotes."""
        return self.get_by_quality(QuoteQuality.OUTSTANDING)

    @property
    def marketing_ready(self) -> list[Quote]:
        """Get quotes suitable for marketing (outstanding + favorites)."""
        return [q for q in self.quotes
                if q.quality == QuoteQuality.OUTSTANDING or q.is_favorite]

    def get_statistics(self) -> dict:
        """Get statistics about the quote collection."""
        if not self.quotes:
            return {
                "total": 0,
                "by_quality": {},
                "by_category": {},
                "total_reuses": 0,
                "favorites": 0,
            }

        by_quality = {}
        for quality in QuoteQuality:
            count = len([q for q in self.quotes if q.quality == quality])
            if count > 0:
                by_quality[quality.value] = count

        by_category = {}
        for category in QuoteCategory:
            count = len([q for q in self.quotes if category in q.categories])
            if count > 0:
                by_category[category.value] = count

        return {
            "total": len(self.quotes),
            "by_quality": by_quality,
            "by_category": by_category,
            "total_reuses": sum(q.reuse_count for q in self.quotes),
            "favorites": len(self.get_favorites()),
            "unique_talks": len(set(q.talk_id for q in self.quotes)),
        }

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization."""
        return {
            "quotes": [q.to_dict() for q in self.quotes],
            "statistics": self.get_statistics(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "QuoteCollection":
        """Create QuoteCollection from dictionary."""
        quotes = [Quote.from_dict(q) for q in data.get("quotes", [])]
        return cls(quotes=quotes)
