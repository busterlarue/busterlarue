"""
SQLite database layer for persistent storage.
"""

import sqlite3
import json
from pathlib import Path
from datetime import datetime
from typing import Optional
from contextlib import contextmanager

from ..models.talk import Talk, TalkMetadata, Segment, AudienceType
from ..models.quotes import Quote, QuoteCollection, QuoteCategory, QuoteQuality
from ..models.delivery import DeliveryMetrics


class Database:
    """
    SQLite database for storing talks, quotes, and metrics.
    """

    def __init__(self, db_path: str | Path = "./talk_analyzer.db"):
        self.db_path = Path(db_path)
        self._ensure_schema()

    @contextmanager
    def _connection(self):
        """Context manager for database connections."""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        try:
            yield conn
            conn.commit()
        finally:
            conn.close()

    def _ensure_schema(self):
        """Create database tables if they don't exist."""
        with self._connection() as conn:
            cursor = conn.cursor()

            # Talks table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS talks (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    date TEXT NOT NULL,
                    venue TEXT,
                    topic TEXT,
                    audience_type TEXT,
                    audience_size INTEGER,
                    duration_seconds REAL,
                    tags TEXT,  -- JSON array
                    notes TEXT,
                    raw_transcript TEXT,
                    segments TEXT,  -- JSON array
                    created_at TEXT NOT NULL,
                    updated_at TEXT NOT NULL
                )
            """)

            # Quotes table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS quotes (
                    id TEXT PRIMARY KEY,
                    text TEXT NOT NULL,
                    talk_id TEXT NOT NULL,
                    timestamp REAL,
                    context_before TEXT,
                    context_after TEXT,
                    topic_context TEXT,
                    categories TEXT,  -- JSON array
                    quality TEXT,
                    tags TEXT,  -- JSON array
                    reuse_count INTEGER DEFAULT 0,
                    last_used TEXT,
                    used_in_talks TEXT,  -- JSON array
                    used_in_content TEXT,  -- JSON array
                    created_at TEXT NOT NULL,
                    notes TEXT,
                    is_favorite INTEGER DEFAULT 0,
                    FOREIGN KEY (talk_id) REFERENCES talks(id)
                )
            """)

            # Delivery metrics table
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS delivery_metrics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    talk_id TEXT UNIQUE NOT NULL,
                    metrics_json TEXT NOT NULL,  -- Full metrics as JSON
                    overall_score REAL,
                    filler_count INTEGER,
                    fillers_per_minute REAL,
                    average_wpm REAL,
                    created_at TEXT NOT NULL,
                    FOREIGN KEY (talk_id) REFERENCES talks(id)
                )
            """)

            # Talk connections table (for cross-talk analysis)
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS talk_connections (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    source_talk_id TEXT NOT NULL,
                    target_talk_id TEXT NOT NULL,
                    connection_type TEXT NOT NULL,
                    strength REAL,
                    shared_themes TEXT,  -- JSON array
                    notes TEXT,
                    FOREIGN KEY (source_talk_id) REFERENCES talks(id),
                    FOREIGN KEY (target_talk_id) REFERENCES talks(id)
                )
            """)

            # Create indexes for common queries
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_talks_date ON talks(date)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_quotes_talk_id ON quotes(talk_id)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_quotes_quality ON quotes(quality)")
            cursor.execute("CREATE INDEX IF NOT EXISTS idx_quotes_favorite ON quotes(is_favorite)")

    # ============== Talk Operations ==============

    def save_talk(self, talk: Talk) -> str:
        """Save or update a talk."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO talks
                (id, title, date, venue, topic, audience_type, audience_size,
                 duration_seconds, tags, notes, raw_transcript, segments,
                 created_at, updated_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                talk.id,
                talk.metadata.title,
                talk.metadata.date.isoformat(),
                talk.metadata.venue,
                talk.metadata.topic,
                talk.metadata.audience_type.value,
                talk.metadata.audience_size,
                talk.metadata.duration_seconds,
                json.dumps(talk.metadata.tags),
                talk.metadata.notes,
                talk.raw_transcript,
                json.dumps([{
                    "text": s.text,
                    "start_time": s.start_time,
                    "end_time": s.end_time,
                    "segment_index": s.segment_index,
                } for s in talk.segments]),
                talk.created_at.isoformat(),
                datetime.now().isoformat(),
            ))
        return talk.id

    def get_talk(self, talk_id: str) -> Optional[Talk]:
        """Retrieve a talk by ID."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM talks WHERE id = ?", (talk_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_talk(row)

    def get_all_talks(self, limit: int = 100, offset: int = 0) -> list[Talk]:
        """Get all talks, ordered by date descending."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM talks ORDER BY date DESC LIMIT ? OFFSET ?",
                (limit, offset)
            )
            return [self._row_to_talk(row) for row in cursor.fetchall()]

    def search_talks(self, query: str) -> list[Talk]:
        """Search talks by title, topic, or transcript content."""
        with self._connection() as conn:
            cursor = conn.cursor()
            search_pattern = f"%{query}%"
            cursor.execute("""
                SELECT * FROM talks
                WHERE title LIKE ? OR topic LIKE ? OR raw_transcript LIKE ?
                ORDER BY date DESC
            """, (search_pattern, search_pattern, search_pattern))
            return [self._row_to_talk(row) for row in cursor.fetchall()]

    def delete_talk(self, talk_id: str) -> bool:
        """Delete a talk and its associated data."""
        with self._connection() as conn:
            cursor = conn.cursor()
            # Delete associated quotes and metrics
            cursor.execute("DELETE FROM quotes WHERE talk_id = ?", (talk_id,))
            cursor.execute("DELETE FROM delivery_metrics WHERE talk_id = ?", (talk_id,))
            cursor.execute("DELETE FROM talk_connections WHERE source_talk_id = ? OR target_talk_id = ?",
                          (talk_id, talk_id))
            cursor.execute("DELETE FROM talks WHERE id = ?", (talk_id,))
            return cursor.rowcount > 0

    def _row_to_talk(self, row: sqlite3.Row) -> Talk:
        """Convert a database row to a Talk object."""
        segments_data = json.loads(row["segments"]) if row["segments"] else []
        segments = [
            Segment(
                text=s["text"],
                start_time=s.get("start_time"),
                end_time=s.get("end_time"),
                segment_index=s.get("segment_index", i),
            )
            for i, s in enumerate(segments_data)
        ]

        metadata = TalkMetadata(
            title=row["title"],
            date=datetime.fromisoformat(row["date"]),
            venue=row["venue"],
            topic=row["topic"],
            audience_type=AudienceType(row["audience_type"]) if row["audience_type"] else AudienceType.OTHER,
            audience_size=row["audience_size"],
            duration_seconds=row["duration_seconds"],
            tags=json.loads(row["tags"]) if row["tags"] else [],
            notes=row["notes"],
        )

        return Talk(
            id=row["id"],
            metadata=metadata,
            raw_transcript=row["raw_transcript"] or "",
            segments=segments,
            created_at=datetime.fromisoformat(row["created_at"]),
            updated_at=datetime.fromisoformat(row["updated_at"]),
        )

    # ============== Quote Operations ==============

    def save_quote(self, quote: Quote) -> str:
        """Save or update a quote."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO quotes
                (id, text, talk_id, timestamp, context_before, context_after,
                 topic_context, categories, quality, tags, reuse_count,
                 last_used, used_in_talks, used_in_content, created_at, notes, is_favorite)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                quote.id,
                quote.text,
                quote.talk_id,
                quote.timestamp,
                quote.context_before,
                quote.context_after,
                quote.topic_context,
                json.dumps([c.value for c in quote.categories]),
                quote.quality.value,
                json.dumps(quote.tags),
                quote.reuse_count,
                quote.last_used.isoformat() if quote.last_used else None,
                json.dumps(quote.used_in_talks),
                json.dumps(quote.used_in_content),
                quote.created_at.isoformat(),
                quote.notes,
                1 if quote.is_favorite else 0,
            ))
        return quote.id

    def save_quotes(self, quotes: list[Quote]) -> int:
        """Save multiple quotes at once."""
        count = 0
        for quote in quotes:
            self.save_quote(quote)
            count += 1
        return count

    def get_quote(self, quote_id: str) -> Optional[Quote]:
        """Retrieve a quote by ID."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM quotes WHERE id = ?", (quote_id,))
            row = cursor.fetchone()
            if not row:
                return None
            return self._row_to_quote(row)

    def get_quotes_for_talk(self, talk_id: str) -> QuoteCollection:
        """Get all quotes from a specific talk."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM quotes WHERE talk_id = ? ORDER BY timestamp",
                (talk_id,)
            )
            quotes = [self._row_to_quote(row) for row in cursor.fetchall()]
            return QuoteCollection(quotes=quotes)

    def get_all_quotes(self, limit: int = 100, offset: int = 0) -> QuoteCollection:
        """Get all quotes."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM quotes ORDER BY created_at DESC LIMIT ? OFFSET ?",
                (limit, offset)
            )
            quotes = [self._row_to_quote(row) for row in cursor.fetchall()]
            return QuoteCollection(quotes=quotes)

    def get_favorite_quotes(self) -> QuoteCollection:
        """Get all favorite quotes."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM quotes WHERE is_favorite = 1")
            quotes = [self._row_to_quote(row) for row in cursor.fetchall()]
            return QuoteCollection(quotes=quotes)

    def get_outstanding_quotes(self) -> QuoteCollection:
        """Get all outstanding quality quotes."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM quotes WHERE quality = 'outstanding'")
            quotes = [self._row_to_quote(row) for row in cursor.fetchall()]
            return QuoteCollection(quotes=quotes)

    def search_quotes(self, query: str) -> QuoteCollection:
        """Search quotes by text content."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT * FROM quotes WHERE text LIKE ?",
                (f"%{query}%",)
            )
            quotes = [self._row_to_quote(row) for row in cursor.fetchall()]
            return QuoteCollection(quotes=quotes)

    def _row_to_quote(self, row: sqlite3.Row) -> Quote:
        """Convert a database row to a Quote object."""
        return Quote(
            id=row["id"],
            text=row["text"],
            talk_id=row["talk_id"],
            timestamp=row["timestamp"],
            context_before=row["context_before"] or "",
            context_after=row["context_after"] or "",
            topic_context=row["topic_context"] or "",
            categories=[QuoteCategory(c) for c in json.loads(row["categories"] or "[]")],
            quality=QuoteQuality(row["quality"]) if row["quality"] else QuoteQuality.GOOD,
            tags=json.loads(row["tags"] or "[]"),
            reuse_count=row["reuse_count"] or 0,
            last_used=datetime.fromisoformat(row["last_used"]) if row["last_used"] else None,
            used_in_talks=json.loads(row["used_in_talks"] or "[]"),
            used_in_content=json.loads(row["used_in_content"] or "[]"),
            created_at=datetime.fromisoformat(row["created_at"]),
            notes=row["notes"] or "",
            is_favorite=bool(row["is_favorite"]),
        )

    # ============== Delivery Metrics Operations ==============

    def save_delivery_metrics(self, metrics: DeliveryMetrics) -> None:
        """Save delivery metrics for a talk."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT OR REPLACE INTO delivery_metrics
                (talk_id, metrics_json, overall_score, filler_count,
                 fillers_per_minute, average_wpm, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                metrics.talk_id,
                json.dumps(metrics.to_dict()),
                metrics.overall_delivery_score,
                metrics.filler_analysis.total_count,
                metrics.filler_analysis.fillers_per_minute,
                metrics.pacing_analysis.average_wpm,
                datetime.now().isoformat(),
            ))

    def get_delivery_metrics(self, talk_id: str) -> Optional[dict]:
        """Get delivery metrics for a talk (as dictionary)."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute(
                "SELECT metrics_json FROM delivery_metrics WHERE talk_id = ?",
                (talk_id,)
            )
            row = cursor.fetchone()
            if not row:
                return None
            return json.loads(row["metrics_json"])

    def get_metrics_history(self) -> list[dict]:
        """Get delivery metrics history for trend analysis."""
        with self._connection() as conn:
            cursor = conn.cursor()
            cursor.execute("""
                SELECT dm.*, t.date, t.title
                FROM delivery_metrics dm
                JOIN talks t ON dm.talk_id = t.id
                ORDER BY t.date
            """)
            return [dict(row) for row in cursor.fetchall()]

    # ============== Statistics ==============

    def get_statistics(self) -> dict:
        """Get overall database statistics."""
        with self._connection() as conn:
            cursor = conn.cursor()

            cursor.execute("SELECT COUNT(*) as count FROM talks")
            talk_count = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) as count FROM quotes")
            quote_count = cursor.fetchone()["count"]

            cursor.execute("SELECT COUNT(*) as count FROM quotes WHERE is_favorite = 1")
            favorite_count = cursor.fetchone()["count"]

            cursor.execute("SELECT AVG(overall_score) as avg FROM delivery_metrics")
            avg_score = cursor.fetchone()["avg"] or 0

            cursor.execute("SELECT MIN(date) as first, MAX(date) as last FROM talks")
            date_row = cursor.fetchone()

            return {
                "total_talks": talk_count,
                "total_quotes": quote_count,
                "favorite_quotes": favorite_count,
                "average_delivery_score": round(avg_score, 1),
                "first_talk_date": date_row["first"],
                "last_talk_date": date_row["last"],
            }
