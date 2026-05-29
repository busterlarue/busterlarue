"""
Configuration settings for the Talk Transcript Analyzer.
"""

from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional
import os


@dataclass
class AnalyzerConfig:
    """Configuration for the transcript analyzer."""

    # Storage
    database_path: Path = field(default_factory=lambda: Path("./talk_analyzer.db"))
    export_dir: Path = field(default_factory=lambda: Path("./exports"))

    # Filler word detection
    filler_words: list[str] = field(default_factory=lambda: [
        "um", "uh", "er", "ah", "like", "you know", "sort of", "kind of",
        "basically", "actually", "literally", "right", "so", "well",
        "I mean", "you see", "okay so"
    ])

    # Pacing thresholds (words per minute)
    pacing_slow_threshold: int = 100  # Below this is considered slow
    pacing_fast_threshold: int = 160  # Above this is considered rushed
    pacing_optimal_min: int = 120
    pacing_optimal_max: int = 150

    # Pause detection (seconds)
    pause_significant_threshold: float = 2.0  # Pauses longer than this are "significant"
    pause_dramatic_threshold: float = 4.0     # Pauses longer than this are "dramatic"

    # Quote extraction
    quote_min_words: int = 8
    quote_max_words: int = 50

    # Segment analysis (seconds)
    segment_duration: int = 60  # Analyze in 1-minute segments by default

    # Integration settings (loaded from environment)
    notion_api_key: Optional[str] = field(default_factory=lambda: os.getenv("NOTION_API_KEY"))
    notion_database_id: Optional[str] = field(default_factory=lambda: os.getenv("NOTION_DATABASE_ID"))

    sendgrid_api_key: Optional[str] = field(default_factory=lambda: os.getenv("SENDGRID_API_KEY"))
    smtp_host: Optional[str] = field(default_factory=lambda: os.getenv("SMTP_HOST"))
    smtp_port: int = field(default_factory=lambda: int(os.getenv("SMTP_PORT", "587")))
    smtp_user: Optional[str] = field(default_factory=lambda: os.getenv("SMTP_USER"))
    smtp_password: Optional[str] = field(default_factory=lambda: os.getenv("SMTP_PASSWORD"))

    email_from: Optional[str] = field(default_factory=lambda: os.getenv("EMAIL_FROM"))


# Default configuration instance
default_config = AnalyzerConfig()
