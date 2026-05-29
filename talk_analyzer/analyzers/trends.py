"""
Cross-talk analysis and trend tracking.
"""

from typing import Optional
from collections import defaultdict
import re

from ..models.talk import Talk
from ..models.delivery import DeliveryMetrics
from ..models.quotes import QuoteCollection
from ..models.trends import (
    TrendAnalysis, TrendDirection, TopicFrequency,
    DeliveryTrend, TalkConnection, ConnectionType,
    RecurringInsight, AudiencePattern,
)
from ..storage.database import Database


class TrendAnalyzer:
    """
    Analyze trends and connections across multiple talks.
    """

    def __init__(self, database: Database):
        self.db = database

    def analyze_trends(self, talks: Optional[list[Talk]] = None) -> TrendAnalysis:
        """
        Perform comprehensive trend analysis across talks.
        """
        if talks is None:
            talks = self.db.get_all_talks(limit=1000)

        if not talks:
            return TrendAnalysis()

        analysis = TrendAnalysis()

        # Set time range
        dates = [t.metadata.date for t in talks]
        analysis.analysis_start = min(dates)
        analysis.analysis_end = max(dates)
        analysis.total_talks_analyzed = len(talks)

        # Analyze topics
        self._analyze_topics(talks, analysis)

        # Analyze delivery trends
        self._analyze_delivery_trends(talks, analysis)

        # Find talk connections
        self._find_connections(talks, analysis)

        # Analyze by audience type
        self._analyze_audience_patterns(talks, analysis)

        # Generate insights
        self._generate_insights(analysis)

        return analysis

    def _analyze_topics(self, talks: list[Talk], analysis: TrendAnalysis):
        """Analyze topic frequency and trends across talks."""
        from .content import ContentAnalyzer

        content_analyzer = ContentAnalyzer()
        topic_data = defaultdict(lambda: {"mentions": 0, "talks": set(), "dates": []})

        for talk in talks:
            themes = content_analyzer.extract_themes(talk, top_n=15)
            for theme, count in themes:
                topic_data[theme]["mentions"] += count
                topic_data[theme]["talks"].add(talk.id)
                topic_data[theme]["dates"].append(talk.metadata.date)

        # Convert to TopicFrequency objects
        for topic, data in topic_data.items():
            if data["mentions"] >= 5:  # Minimum threshold
                tf = TopicFrequency(
                    topic=topic,
                    total_mentions=data["mentions"],
                    talks_mentioned_in=list(data["talks"]),
                    first_mentioned=min(data["dates"]) if data["dates"] else None,
                    last_mentioned=max(data["dates"]) if data["dates"] else None,
                )
                analysis.topic_frequencies.append(tf)

        # Sort by total mentions
        analysis.topic_frequencies.sort(key=lambda x: x.total_mentions, reverse=True)

        # Identify emerging and declining topics
        if len(talks) >= 5:
            mid_point = len(talks) // 2
            earlier_talks = talks[:mid_point]
            later_talks = talks[mid_point:]

            earlier_topics = self._get_topic_set(earlier_talks, content_analyzer)
            later_topics = self._get_topic_set(later_talks, content_analyzer)

            # Emerging: in later but not earlier (or much more frequent)
            for topic in later_topics - earlier_topics:
                if topic not in analysis.emerging_topics:
                    analysis.emerging_topics.append(topic)

            # Declining: in earlier but not later
            for topic in earlier_topics - later_topics:
                if topic not in analysis.declining_topics:
                    analysis.declining_topics.append(topic)

    def _get_topic_set(self, talks: list[Talk], analyzer) -> set:
        """Get set of significant topics from a list of talks."""
        topics = set()
        for talk in talks:
            themes = analyzer.extract_themes(talk, top_n=5)
            for theme, count in themes:
                if count >= 3:
                    topics.add(theme)
        return topics

    def _analyze_delivery_trends(self, talks: list[Talk], analysis: TrendAnalysis):
        """Analyze delivery metrics over time."""
        # Sort talks by date
        sorted_talks = sorted(talks, key=lambda t: t.metadata.date)

        # Collect metrics for each talk
        metrics_data = {
            "fillers_per_minute": [],
            "average_wpm": [],
            "pacing_consistency": [],
            "overall_score": [],
        }

        for talk in sorted_talks:
            metrics_dict = self.db.get_delivery_metrics(talk.id)
            if metrics_dict:
                date = talk.metadata.date

                if "filler_analysis" in metrics_dict:
                    fpm = metrics_dict["filler_analysis"].get("fillers_per_minute", 0)
                    metrics_data["fillers_per_minute"].append((date, fpm))

                if "pacing_analysis" in metrics_dict:
                    wpm = metrics_dict["pacing_analysis"].get("average_wpm", 0)
                    consistency = metrics_dict["pacing_analysis"].get("consistency_score", 0)
                    metrics_data["average_wpm"].append((date, wpm))
                    metrics_data["pacing_consistency"].append((date, consistency))

                overall = metrics_dict.get("overall_score", 0)
                if overall:
                    metrics_data["overall_score"].append((date, overall))

        # Create trend objects
        for metric_name, data_points in metrics_data.items():
            if len(data_points) >= 2:
                trend = DeliveryTrend(metric_name=metric_name)
                for date, value in data_points:
                    trend.add_data_point(date, value)
                analysis.delivery_trends[metric_name] = trend

    def _find_connections(self, talks: list[Talk], analysis: TrendAnalysis):
        """Find thematic connections between talks."""
        from .content import ContentAnalyzer

        content_analyzer = ContentAnalyzer()

        # Extract themes for each talk
        talk_themes = {}
        for talk in talks:
            themes = content_analyzer.extract_themes(talk, top_n=10)
            talk_themes[talk.id] = {theme for theme, _ in themes}

        # Find connections based on shared themes
        talk_list = list(talks)
        for i, talk1 in enumerate(talk_list):
            for talk2 in talk_list[i + 1:]:
                themes1 = talk_themes.get(talk1.id, set())
                themes2 = talk_themes.get(talk2.id, set())

                shared = themes1 & themes2

                if len(shared) >= 3:  # At least 3 shared themes
                    # Calculate strength based on overlap
                    union = themes1 | themes2
                    strength = len(shared) / len(union) if union else 0

                    # Determine connection type
                    if talk1.metadata.topic and talk2.metadata.topic:
                        if talk1.metadata.topic == talk2.metadata.topic:
                            conn_type = ConnectionType.EVOLVED
                        else:
                            conn_type = ConnectionType.THEMATIC
                    else:
                        conn_type = ConnectionType.THEMATIC

                    connection = TalkConnection(
                        source_talk_id=talk1.id,
                        target_talk_id=talk2.id,
                        connection_type=conn_type,
                        strength=strength,
                        shared_themes=list(shared)[:5],
                    )
                    analysis.talk_connections.append(connection)

    def _analyze_audience_patterns(self, talks: list[Talk], analysis: TrendAnalysis):
        """Analyze patterns by audience type."""
        from .content import ContentAnalyzer

        audience_data = defaultdict(lambda: {
            "count": 0,
            "scores": [],
            "themes": [],
            "quotes": [],
        })

        content_analyzer = ContentAnalyzer()

        for talk in talks:
            audience = talk.metadata.audience_type.value

            audience_data[audience]["count"] += 1

            # Get delivery metrics
            metrics = self.db.get_delivery_metrics(talk.id)
            if metrics and "overall_score" in metrics:
                audience_data[audience]["scores"].append(metrics["overall_score"])

            # Get themes
            themes = content_analyzer.extract_themes(talk, top_n=5)
            for theme, _ in themes:
                audience_data[audience]["themes"].append(theme)

            # Get outstanding quotes
            quotes = self.db.get_quotes_for_talk(talk.id)
            for quote in quotes.outstanding_quotes:
                audience_data[audience]["quotes"].append(quote.id)

        # Create pattern objects
        for audience, data in audience_data.items():
            if data["count"] >= 2:  # At least 2 talks
                avg_score = sum(data["scores"]) / len(data["scores"]) if data["scores"] else 0

                # Get most common themes
                from collections import Counter
                theme_counts = Counter(data["themes"])
                common_themes = [t for t, _ in theme_counts.most_common(5)]

                pattern = AudiencePattern(
                    audience_type=audience,
                    talk_count=data["count"],
                    average_delivery_score=avg_score,
                    common_themes=common_themes,
                    best_performing_quotes=data["quotes"][:5],
                )
                analysis.audience_patterns.append(pattern)

    def _generate_insights(self, analysis: TrendAnalysis):
        """Generate key findings and recommendations."""
        findings = []
        recommendations = []

        # Delivery trend insights
        if "fillers_per_minute" in analysis.delivery_trends:
            filler_trend = analysis.delivery_trends["fillers_per_minute"]
            if filler_trend.direction == TrendDirection.IMPROVING:
                findings.append(
                    f"Filler word usage has decreased by {abs(filler_trend.improvement_percentage):.0f}% over time"
                )
            elif filler_trend.direction == TrendDirection.DECLINING:
                findings.append(
                    f"Filler word usage has increased by {filler_trend.improvement_percentage:.0f}% over time"
                )
                recommendations.append("Focus on reducing filler words in upcoming talks")

        if "overall_score" in analysis.delivery_trends:
            score_trend = analysis.delivery_trends["overall_score"]
            if score_trend.direction == TrendDirection.IMPROVING:
                findings.append(
                    f"Overall delivery scores have improved by {score_trend.improvement_percentage:.0f}%"
                )
            elif score_trend.direction == TrendDirection.DECLINING:
                recommendations.append("Review recent talks for delivery improvement opportunities")

        # Topic insights
        if analysis.topic_frequencies:
            top_topics = analysis.topic_frequencies[:3]
            topic_names = [t.topic for t in top_topics]
            findings.append(f"Core topics across talks: {', '.join(topic_names)}")

        if analysis.emerging_topics:
            findings.append(f"Emerging topics: {', '.join(analysis.emerging_topics[:3])}")

        if analysis.declining_topics:
            findings.append(f"Topics receiving less focus: {', '.join(analysis.declining_topics[:3])}")

        # Connection insights
        if analysis.talk_connections:
            strong_connections = [c for c in analysis.talk_connections if c.strength > 0.4]
            if strong_connections:
                findings.append(f"Found {len(strong_connections)} strongly connected talk pairs")

        # Audience insights
        if len(analysis.audience_patterns) > 1:
            best_audience = max(
                analysis.audience_patterns,
                key=lambda p: p.average_delivery_score
            )
            if best_audience.average_delivery_score > 0:
                findings.append(
                    f"Highest delivery scores with {best_audience.audience_type} audiences "
                    f"({best_audience.average_delivery_score:.0f}/100)"
                )

        analysis.key_findings = findings
        analysis.recommendations = recommendations

    def compare_talks(self, talk1: Talk, talk2: Talk) -> dict:
        """
        Compare two talks directly.
        """
        from .content import ContentAnalyzer
        from .delivery import DeliveryAnalyzer

        content_analyzer = ContentAnalyzer()
        delivery_analyzer = DeliveryAnalyzer()

        # Get themes
        themes1 = set(t for t, _ in content_analyzer.extract_themes(talk1, top_n=10))
        themes2 = set(t for t, _ in content_analyzer.extract_themes(talk2, top_n=10))

        # Get metrics
        metrics1 = self.db.get_delivery_metrics(talk1.id)
        metrics2 = self.db.get_delivery_metrics(talk2.id)

        shared_themes = themes1 & themes2
        unique_to_1 = themes1 - themes2
        unique_to_2 = themes2 - themes1

        comparison = {
            "talk1": {
                "id": talk1.id,
                "title": talk1.metadata.title,
                "date": talk1.metadata.date.isoformat(),
                "word_count": talk1.word_count,
            },
            "talk2": {
                "id": talk2.id,
                "title": talk2.metadata.title,
                "date": talk2.metadata.date.isoformat(),
                "word_count": talk2.word_count,
            },
            "thematic_overlap": {
                "shared_themes": list(shared_themes),
                "unique_to_talk1": list(unique_to_1),
                "unique_to_talk2": list(unique_to_2),
                "similarity_score": len(shared_themes) / len(themes1 | themes2) if themes1 | themes2 else 0,
            },
        }

        # Compare metrics if available
        if metrics1 and metrics2:
            comparison["delivery_comparison"] = {
                "talk1_score": metrics1.get("overall_score", 0),
                "talk2_score": metrics2.get("overall_score", 0),
                "talk1_fillers_per_min": metrics1.get("filler_analysis", {}).get("fillers_per_minute", 0),
                "talk2_fillers_per_min": metrics2.get("filler_analysis", {}).get("fillers_per_minute", 0),
                "talk1_wpm": metrics1.get("pacing_analysis", {}).get("average_wpm", 0),
                "talk2_wpm": metrics2.get("pacing_analysis", {}).get("average_wpm", 0),
            }

        return comparison

    def get_trend_summary(self, analysis: TrendAnalysis) -> str:
        """Generate a human-readable trend summary."""
        lines = []

        lines.append(f"## Trend Analysis Summary")
        lines.append(f"*Analyzing {analysis.total_talks_analyzed} talks*")

        if analysis.analysis_start and analysis.analysis_end:
            lines.append(
                f"*Period: {analysis.analysis_start.strftime('%Y-%m-%d')} to "
                f"{analysis.analysis_end.strftime('%Y-%m-%d')}*"
            )

        lines.append("")

        # Key findings
        if analysis.key_findings:
            lines.append("### Key Findings")
            for finding in analysis.key_findings:
                lines.append(f"- {finding}")
            lines.append("")

        # Top topics
        if analysis.topic_frequencies:
            lines.append("### Top Topics")
            for tf in analysis.topic_frequencies[:5]:
                lines.append(f"- **{tf.topic}**: {tf.total_mentions} mentions across {tf.talk_count} talks")
            lines.append("")

        # Delivery trends
        if analysis.delivery_trends:
            lines.append("### Delivery Trends")
            for name, trend in analysis.delivery_trends.items():
                direction = trend.direction.value.replace("_", " ")
                lines.append(
                    f"- **{name.replace('_', ' ').title()}**: {direction} "
                    f"(latest: {trend.latest_value:.1f})"
                )
            lines.append("")

        # Recommendations
        if analysis.recommendations:
            lines.append("### Recommendations")
            for rec in analysis.recommendations:
                lines.append(f"- {rec}")
            lines.append("")

        return "\n".join(lines)
