"""
After Action Review (AAR) artifact generator.

Generates comprehensive review documents from talk analysis.
"""

from datetime import datetime
from typing import Optional

from ..models.talk import Talk
from ..models.delivery import DeliveryMetrics
from ..models.quotes import QuoteCollection, QuoteQuality
from ..models.trends import TrendAnalysis
from ..analyzers.delivery import DeliveryAnalyzer
from ..analyzers.content import ContentAnalyzer
from ..storage.database import Database


class AfterActionReview:
    """
    Generate After Action Review artifacts from talk analysis.
    """

    def __init__(self, database: Optional[Database] = None):
        self.db = database
        self.delivery_analyzer = DeliveryAnalyzer()
        self.content_analyzer = ContentAnalyzer()

    def generate(
        self,
        talk: Talk,
        metrics: Optional[DeliveryMetrics] = None,
        quotes: Optional[QuoteCollection] = None,
        trends: Optional[TrendAnalysis] = None,
        include_raw_data: bool = False,
    ) -> str:
        """
        Generate a complete After Action Review artifact.

        Args:
            talk: The Talk object to review
            metrics: Pre-computed delivery metrics (will compute if not provided)
            quotes: Pre-extracted quotes (will extract if not provided)
            trends: Cross-talk trends for context (optional)
            include_raw_data: Include raw analysis data at end

        Returns:
            Markdown-formatted AAR document
        """
        # Compute what we need
        if metrics is None:
            metrics = self.delivery_analyzer.analyze(talk)

        if quotes is None:
            quotes = self.content_analyzer.extract_quotes(talk)

        themes = self.content_analyzer.extract_themes(talk)
        key_moments = self.content_analyzer.find_key_moments(talk)

        # Build the document
        sections = []

        # Header
        sections.append(self._generate_header(talk))

        # Executive Summary
        sections.append(self._generate_summary(talk, metrics, quotes, themes))

        # Delivery Analysis
        sections.append(self._generate_delivery_section(metrics))

        # Outstanding Quotes
        sections.append(self._generate_quotes_section(quotes))

        # Key Themes
        sections.append(self._generate_themes_section(themes))

        # Key Moments
        sections.append(self._generate_moments_section(key_moments))

        # Cross-Talk Connections (if trends provided)
        if trends:
            sections.append(self._generate_connections_section(talk, trends))

        # Action Items
        sections.append(self._generate_action_items(talk, metrics, quotes))

        # Raw Data (optional)
        if include_raw_data:
            sections.append(self._generate_raw_data_section(metrics))

        return "\n\n".join(sections)

    def _generate_header(self, talk: Talk) -> str:
        """Generate the AAR header."""
        lines = [
            f"# After Action Review: {talk.metadata.title}",
            "",
            f"**Date:** {talk.metadata.date.strftime('%B %d, %Y')}",
        ]

        if talk.metadata.venue:
            lines.append(f"**Venue:** {talk.metadata.venue}")

        if talk.metadata.topic:
            lines.append(f"**Topic:** {talk.metadata.topic}")

        lines.append(f"**Duration:** {talk.metadata.duration_formatted}")

        if talk.metadata.audience_type:
            audience = talk.metadata.audience_type.value.replace("_", " ").title()
            lines.append(f"**Audience:** {audience}")
            if talk.metadata.audience_size:
                lines[-1] += f" ({talk.metadata.audience_size} attendees)"

        if talk.metadata.tags:
            lines.append(f"**Tags:** {', '.join(talk.metadata.tags)}")

        lines.append("")
        lines.append(f"*Generated: {datetime.now().strftime('%Y-%m-%d %H:%M')}*")

        return "\n".join(lines)

    def _generate_summary(
        self,
        talk: Talk,
        metrics: DeliveryMetrics,
        quotes: QuoteCollection,
        themes: list[tuple[str, int]]
    ) -> str:
        """Generate executive summary section."""
        lines = ["## Executive Summary", ""]

        # Overall assessment
        score = metrics.overall_delivery_score
        if score >= 80:
            assessment = "Excellent delivery"
        elif score >= 60:
            assessment = "Good delivery with some areas for improvement"
        elif score >= 40:
            assessment = "Moderate delivery - several areas need attention"
        else:
            assessment = "Delivery needs significant improvement"

        # Build summary bullets
        summary_points = []

        summary_points.append(
            f"**Overall Delivery Score:** {score:.0f}/100 - {assessment}"
        )

        # Top themes
        if themes:
            top_themes = [t[0] for t in themes[:3]]
            summary_points.append(f"**Core Themes:** {', '.join(top_themes)}")

        # Quote highlights
        outstanding = quotes.outstanding_quotes
        if outstanding:
            summary_points.append(
                f"**Notable Quotes:** {len(outstanding)} outstanding quotes extracted"
            )

        # Key metrics
        filler_rate = metrics.filler_analysis.fillers_per_minute
        if filler_rate < 2:
            summary_points.append(f"**Filler Words:** Excellent ({filler_rate:.1f}/min)")
        elif filler_rate < 4:
            summary_points.append(f"**Filler Words:** Good ({filler_rate:.1f}/min)")
        else:
            summary_points.append(f"**Filler Words:** Needs work ({filler_rate:.1f}/min)")

        wpm = metrics.pacing_analysis.average_wpm
        if wpm:
            summary_points.append(f"**Pacing:** {wpm:.0f} words/minute average")

        for point in summary_points:
            lines.append(f"- {point}")

        return "\n".join(lines)

    def _generate_delivery_section(self, metrics: DeliveryMetrics) -> str:
        """Generate detailed delivery analysis section."""
        lines = ["## Delivery Analysis", ""]

        # Pacing subsection
        lines.append("### Pacing")
        pacing = metrics.pacing_analysis
        lines.append(f"- **Overall:** {pacing.average_wpm:.0f} WPM ({pacing.overall_level.value.replace('_', ' ')})")
        lines.append(f"- **Consistency Score:** {pacing.consistency_score:.0f}%")

        if pacing.rushed_segments:
            lines.append(f"- **Rushed Sections:** {len(pacing.rushed_segments)}")
            for seg in pacing.rushed_segments[:3]:
                lines.append(f"  - {seg.timestamp_formatted} ({seg.words_per_minute:.0f} WPM)")

        if pacing.slow_segments:
            lines.append(f"- **Slow Sections:** {len(pacing.slow_segments)}")
            for seg in pacing.slow_segments[:3]:
                lines.append(f"  - {seg.timestamp_formatted} ({seg.words_per_minute:.0f} WPM)")

        lines.append("")

        # Filler words subsection
        lines.append("### Vocal Fillers")
        filler = metrics.filler_analysis
        lines.append(f"- **Total Count:** {filler.total_count}")
        lines.append(f"- **Rate:** {filler.fillers_per_minute:.1f} per minute")
        lines.append(f"- **Assessment:** {filler.assessment}")

        if filler.filler_counts:
            lines.append("- **Breakdown:**")
            sorted_fillers = sorted(filler.filler_counts.items(), key=lambda x: x[1], reverse=True)
            for word, count in sorted_fillers[:5]:
                lines.append(f"  - \"{word}\": {count}x")

        hotspots = filler.get_hotspots()
        if hotspots:
            lines.append("- **High-Filler Zones:**")
            for timestamp, count in hotspots[:3]:
                minutes = int(timestamp // 60)
                seconds = int(timestamp % 60)
                lines.append(f"  - {minutes}:{seconds:02d} ({count} fillers in 60s)")

        lines.append("")

        # Pauses subsection
        lines.append("### Pauses")
        pause = metrics.pause_analysis
        lines.append(f"- **Significant Pauses (2+ sec):** {len(pause.significant_pauses)}")
        lines.append(f"- **Dramatic Pauses (4+ sec):** {len(pause.dramatic_pauses)}")

        if pause.dramatic_pauses:
            lines.append("- **Notable Pauses:**")
            for p in pause.dramatic_pauses[:3]:
                lines.append(
                    f"  - {p.timestamp_formatted} ({p.duration:.1f}s) - "
                    f"Before: \"{p.preceding_text[-40:]}...\""
                )

        lines.append("")

        # Energy subsection
        lines.append("### Energy & Tone")
        energy = metrics.energy_analysis
        lines.append(f"- **Average Energy:** {energy.average_level.value.title()}")
        lines.append(f"- **Variation Score:** {energy.energy_variation_score:.0f}%")

        if energy.peak_moments:
            lines.append(f"- **Peak Moments:** {len(energy.peak_moments)}")
            for peak in energy.peak_moments[:3]:
                lines.append(f"  - {peak.timestamp_formatted}: \"{peak.context}\"")

        if metrics.tone_shifts:
            lines.append(f"- **Tone Shifts:** {len(metrics.tone_shifts)}")
            for shift in metrics.tone_shifts[:3]:
                lines.append(
                    f"  - {shift.timestamp_formatted}: "
                    f"{shift.from_tone.value} → {shift.to_tone.value}"
                )

        return "\n".join(lines)

    def _generate_quotes_section(self, quotes: QuoteCollection) -> str:
        """Generate quotes section."""
        lines = ["## Outstanding Quotes", ""]

        # Outstanding quotes first
        outstanding = quotes.outstanding_quotes
        if outstanding:
            for quote in outstanding[:5]:
                lines.append(f"> \"{quote.text}\"")
                lines.append(">")
                meta_parts = []
                if quote.timestamp_formatted:
                    meta_parts.append(f"@{quote.timestamp_formatted}")
                if quote.categories:
                    tags = " ".join(f"`{c.value}`" for c in quote.categories)
                    meta_parts.append(tags)
                lines.append(f"> *{' | '.join(meta_parts)}*")
                lines.append("")

        # Excellent quotes
        excellent = [q for q in quotes.quotes if q.quality == QuoteQuality.EXCELLENT]
        if excellent:
            lines.append("### Excellent Quotes")
            lines.append("")
            for quote in excellent[:5]:
                lines.append(f"> \"{quote.text}\"")
                lines.append(">")
                meta_parts = []
                if quote.timestamp_formatted:
                    meta_parts.append(f"@{quote.timestamp_formatted}")
                if quote.categories:
                    tags = " ".join(f"`{c.value}`" for c in quote.categories)
                    meta_parts.append(tags)
                lines.append(f"> *{' | '.join(meta_parts)}*")
                lines.append("")

        # Summary stats
        stats = quotes.get_statistics()
        lines.append("### Quote Statistics")
        lines.append(f"- Total quotes extracted: {stats['total']}")
        if stats.get('by_quality'):
            for quality, count in stats['by_quality'].items():
                lines.append(f"  - {quality}: {count}")

        return "\n".join(lines)

    def _generate_themes_section(self, themes: list[tuple[str, int]]) -> str:
        """Generate themes section."""
        lines = ["## Key Themes", ""]

        if themes:
            for theme, count in themes[:10]:
                lines.append(f"- **{theme}** - mentioned {count} times")
        else:
            lines.append("*No significant themes identified*")

        return "\n".join(lines)

    def _generate_moments_section(self, moments: list[dict]) -> str:
        """Generate key moments section."""
        lines = ["## Key Moments", ""]

        opening = next((m for m in moments if m["type"] == "opening"), None)
        if opening:
            lines.append("### Opening")
            lines.append(f"- **Style:** {opening.get('analysis', 'N/A')}")
            lines.append(f"- **Text:** \"{opening['text'][:100]}...\"")
            lines.append("")

        transitions = [m for m in moments if m["type"] == "transition"]
        if transitions:
            lines.append("### Transitions")
            for t in transitions[:5]:
                timestamp = t.get("timestamp")
                if timestamp:
                    minutes = int(timestamp // 60)
                    seconds = int(timestamp % 60)
                    lines.append(f"- {minutes}:{seconds:02d}: \"{t['text'][:60]}...\"")
            lines.append("")

        conclusion = next((m for m in moments if m["type"] == "conclusion"), None)
        if conclusion:
            lines.append("### Conclusion")
            lines.append(f"- **Style:** {conclusion.get('analysis', 'N/A')}")
            lines.append(f"- **Text:** \"{conclusion['text'][:100]}...\"")

        return "\n".join(lines)

    def _generate_connections_section(self, talk: Talk, trends: TrendAnalysis) -> str:
        """Generate cross-talk connections section."""
        lines = ["## Cross-Talk Connections", ""]

        connections = trends.get_connections_for_talk(talk.id)

        if connections:
            lines.append("### Related Talks")
            for conn in connections[:5]:
                other_id = conn.target_talk_id if conn.source_talk_id == talk.id else conn.source_talk_id

                # Try to get other talk title
                other_title = other_id
                if self.db:
                    other_talk = self.db.get_talk(other_id)
                    if other_talk:
                        other_title = other_talk.metadata.title

                lines.append(
                    f"- **{other_title}** ({conn.connection_type.value}, "
                    f"strength: {conn.strength:.0%})"
                )
                if conn.shared_themes:
                    lines.append(f"  - Shared themes: {', '.join(conn.shared_themes[:3])}")
            lines.append("")

        # Trend context
        if trends.key_findings:
            lines.append("### Trend Context")
            for finding in trends.key_findings[:3]:
                lines.append(f"- {finding}")

        return "\n".join(lines)

    def _generate_action_items(
        self,
        talk: Talk,
        metrics: DeliveryMetrics,
        quotes: QuoteCollection
    ) -> str:
        """Generate actionable recommendations."""
        lines = ["## Action Items", ""]

        items = []

        # Delivery improvements
        if metrics.filler_analysis.fillers_per_minute >= 4:
            most_common = metrics.filler_analysis.most_common_filler
            items.append(
                f"[ ] Practice reducing filler words, especially \"{most_common}\""
            )

        if metrics.pacing_analysis.rushed_segments:
            items.append(
                f"[ ] Work on slowing down in {len(metrics.pacing_analysis.rushed_segments)} rushed sections"
            )

        if metrics.pacing_analysis.consistency_score < 70:
            items.append("[ ] Focus on maintaining more consistent pacing throughout")

        if len(metrics.pause_analysis.significant_pauses) < 3:
            items.append("[ ] Consider adding more strategic pauses for emphasis")

        # Quote opportunities
        outstanding = quotes.outstanding_quotes
        if outstanding:
            items.append(f"[ ] Review and polish {len(outstanding)} outstanding quotes for reuse")

        marketing_ready = quotes.marketing_ready
        if marketing_ready:
            items.append(f"[ ] Add {len(marketing_ready)} quotes to marketing materials library")

        # Content opportunities
        items.append("[ ] Review extracted themes for content development opportunities")
        items.append("[ ] Identify sections that could become standalone content pieces")

        if not items:
            items.append("[ ] Continue refining delivery based on this analysis")

        for item in items:
            lines.append(f"- {item}")

        return "\n".join(lines)

    def _generate_raw_data_section(self, metrics: DeliveryMetrics) -> str:
        """Generate raw data appendix."""
        import json

        lines = ["## Appendix: Raw Analysis Data", ""]
        lines.append("```json")
        lines.append(json.dumps(metrics.to_dict(), indent=2, default=str))
        lines.append("```")

        return "\n".join(lines)

    def generate_comparison_report(self, talk1: Talk, talk2: Talk) -> str:
        """Generate a comparison report between two talks."""
        from ..analyzers.trends import TrendAnalyzer

        if not self.db:
            return "Database required for comparison reports"

        analyzer = TrendAnalyzer(self.db)
        comparison = analyzer.compare_talks(talk1, talk2)

        lines = [
            "# Talk Comparison Report",
            "",
            f"## {talk1.metadata.title} vs {talk2.metadata.title}",
            "",
            "### Basic Info",
            "",
            f"| Metric | Talk 1 | Talk 2 |",
            f"|--------|--------|--------|",
            f"| Date | {talk1.metadata.date.strftime('%Y-%m-%d')} | {talk2.metadata.date.strftime('%Y-%m-%d')} |",
            f"| Word Count | {talk1.word_count} | {talk2.word_count} |",
            f"| Duration | {talk1.metadata.duration_formatted} | {talk2.metadata.duration_formatted} |",
            "",
        ]

        # Thematic comparison
        overlap = comparison.get("thematic_overlap", {})
        lines.append("### Thematic Analysis")
        lines.append("")
        lines.append(f"**Similarity Score:** {overlap.get('similarity_score', 0):.0%}")
        lines.append("")

        shared = overlap.get("shared_themes", [])
        if shared:
            lines.append(f"**Shared Themes:** {', '.join(shared[:5])}")

        unique1 = overlap.get("unique_to_talk1", [])
        if unique1:
            lines.append(f"**Unique to Talk 1:** {', '.join(unique1[:5])}")

        unique2 = overlap.get("unique_to_talk2", [])
        if unique2:
            lines.append(f"**Unique to Talk 2:** {', '.join(unique2[:5])}")

        lines.append("")

        # Delivery comparison
        delivery = comparison.get("delivery_comparison", {})
        if delivery:
            lines.append("### Delivery Comparison")
            lines.append("")
            lines.append(f"| Metric | Talk 1 | Talk 2 |")
            lines.append(f"|--------|--------|--------|")
            lines.append(
                f"| Overall Score | {delivery.get('talk1_score', 0):.0f} | "
                f"{delivery.get('talk2_score', 0):.0f} |"
            )
            lines.append(
                f"| Fillers/min | {delivery.get('talk1_fillers_per_min', 0):.1f} | "
                f"{delivery.get('talk2_fillers_per_min', 0):.1f} |"
            )
            lines.append(
                f"| Avg WPM | {delivery.get('talk1_wpm', 0):.0f} | "
                f"{delivery.get('talk2_wpm', 0):.0f} |"
            )

        return "\n".join(lines)
