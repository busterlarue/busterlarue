"""
Export functionality for talks, quotes, and analytics.
"""

import json
from pathlib import Path
from datetime import datetime
from typing import Optional

from ..models.talk import Talk
from ..models.quotes import QuoteCollection
from ..models.delivery import DeliveryMetrics


class Exporter:
    """
    Export talks and analysis to various formats.
    """

    def __init__(self, export_dir: str | Path = "./exports"):
        self.export_dir = Path(export_dir)
        self.export_dir.mkdir(parents=True, exist_ok=True)

    def export_talk_json(self, talk: Talk, filename: Optional[str] = None) -> Path:
        """Export a talk to JSON format."""
        if not filename:
            safe_title = "".join(c if c.isalnum() else "_" for c in talk.metadata.title)
            date_str = talk.metadata.date.strftime("%Y%m%d")
            filename = f"talk_{date_str}_{safe_title}.json"

        filepath = self.export_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(talk.to_dict(), f, indent=2, ensure_ascii=False)
        return filepath

    def export_quotes_json(self, quotes: QuoteCollection, filename: str = "quotes.json") -> Path:
        """Export quotes collection to JSON."""
        filepath = self.export_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(quotes.to_dict(), f, indent=2, ensure_ascii=False)
        return filepath

    def export_quotes_markdown(self, quotes: QuoteCollection, filename: str = "quotes.md") -> Path:
        """Export quotes to Markdown format for easy reading."""
        filepath = self.export_dir / filename
        lines = ["# Quote Collection\n"]
        lines.append(f"*Exported: {datetime.now().strftime('%Y-%m-%d %H:%M')}*\n")

        stats = quotes.get_statistics()
        lines.append(f"**Total Quotes:** {stats['total']}\n")
        lines.append(f"**Favorites:** {stats['favorites']}\n")
        lines.append(f"**Total Reuses:** {stats['total_reuses']}\n\n")

        # Group by quality
        lines.append("## Outstanding Quotes\n")
        for quote in quotes.outstanding_quotes:
            lines.append(self._format_quote_markdown(quote))

        lines.append("\n## All Quotes\n")
        for quote in sorted(quotes.quotes, key=lambda q: q.created_at, reverse=True):
            lines.append(self._format_quote_markdown(quote))

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return filepath

    def _format_quote_markdown(self, quote) -> str:
        """Format a single quote as Markdown."""
        lines = []
        favorite = " :star:" if quote.is_favorite else ""
        lines.append(f"> \"{quote.text}\"{favorite}")
        lines.append(f">")
        meta = []
        if quote.timestamp_formatted:
            meta.append(f"@{quote.timestamp_formatted}")
        meta.append(f"Quality: {quote.quality.value}")
        if quote.categories:
            tags = " ".join(f"`{c.value}`" for c in quote.categories)
            meta.append(tags)
        lines.append(f"> *{' | '.join(meta)}*\n")
        return "\n".join(lines)

    def export_aar_markdown(self, aar_content: str, talk: Talk) -> Path:
        """Export After Action Review to Markdown file."""
        safe_title = "".join(c if c.isalnum() else "_" for c in talk.metadata.title)
        date_str = talk.metadata.date.strftime("%Y%m%d")
        filename = f"aar_{date_str}_{safe_title}.md"

        filepath = self.export_dir / filename
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(aar_content)
        return filepath

    def export_metrics_csv(self, metrics_history: list[dict], filename: str = "metrics.csv") -> Path:
        """Export delivery metrics history to CSV for trend analysis."""
        filepath = self.export_dir / filename

        if not metrics_history:
            with open(filepath, "w", encoding="utf-8") as f:
                f.write("date,title,overall_score,filler_count,fillers_per_minute,average_wpm\n")
            return filepath

        lines = ["date,title,overall_score,filler_count,fillers_per_minute,average_wpm"]
        for m in metrics_history:
            title = m.get("title", "").replace(",", ";")
            lines.append(
                f"{m.get('date', '')},{title},{m.get('overall_score', 0)},"
                f"{m.get('filler_count', 0)},{m.get('fillers_per_minute', 0)},"
                f"{m.get('average_wpm', 0)}"
            )

        with open(filepath, "w", encoding="utf-8") as f:
            f.write("\n".join(lines))
        return filepath

    def export_all(
        self,
        talk: Talk,
        quotes: QuoteCollection,
        metrics: DeliveryMetrics,
        aar_content: str
    ) -> dict[str, Path]:
        """Export all data for a talk analysis."""
        safe_title = "".join(c if c.isalnum() else "_" for c in talk.metadata.title)
        date_str = talk.metadata.date.strftime("%Y%m%d")
        prefix = f"{date_str}_{safe_title}"

        return {
            "talk_json": self.export_talk_json(talk, f"{prefix}_talk.json"),
            "quotes_json": self.export_quotes_json(quotes, f"{prefix}_quotes.json"),
            "quotes_md": self.export_quotes_markdown(quotes, f"{prefix}_quotes.md"),
            "aar_md": self.export_aar_markdown(aar_content, talk),
        }
