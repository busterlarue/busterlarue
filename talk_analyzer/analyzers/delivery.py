"""
Delivery analysis: pacing, pauses, fillers, energy, and tone.
"""

import re
from typing import Optional

from ..models.talk import Talk, Segment
from ..models.delivery import (
    DeliveryMetrics,
    FillerAnalysis, FillerInstance,
    PacingAnalysis, PacingSegment, PacingLevel,
    PauseAnalysis, PauseInstance,
    EnergyAnalysis, EnergyPoint, EnergyLevel,
    ToneShift, ToneType,
)
from ..config import default_config, AnalyzerConfig


class DeliveryAnalyzer:
    """
    Analyze speech delivery characteristics from transcripts.
    """

    def __init__(self, config: Optional[AnalyzerConfig] = None):
        self.config = config or default_config

    def analyze(self, talk: Talk) -> DeliveryMetrics:
        """
        Perform complete delivery analysis on a talk.
        """
        metrics = DeliveryMetrics(talk_id=talk.id)

        # Run all analyses
        metrics.filler_analysis = self.analyze_fillers(talk)
        metrics.pacing_analysis = self.analyze_pacing(talk)
        metrics.pause_analysis = self.analyze_pauses(talk)
        metrics.energy_analysis = self.analyze_energy(talk)
        metrics.tone_shifts = self.detect_tone_shifts(talk)

        return metrics

    def analyze_fillers(self, talk: Talk) -> FillerAnalysis:
        """
        Detect and analyze filler words in the transcript.
        """
        analysis = FillerAnalysis()
        text = talk.raw_transcript.lower()

        # Track all filler instances
        instances = []
        filler_counts = {}

        for filler in self.config.filler_words:
            filler_lower = filler.lower()
            # Use word boundaries to avoid false positives
            pattern = r'\b' + re.escape(filler_lower) + r'\b'

            for match in re.finditer(pattern, text, re.IGNORECASE):
                position = match.start()

                # Find timestamp if segments have timing
                timestamp = self._position_to_timestamp(talk, position)

                # Get context (surrounding text)
                context_start = max(0, position - 30)
                context_end = min(len(text), position + len(filler) + 30)
                context = "..." + talk.raw_transcript[context_start:context_end] + "..."

                instances.append(FillerInstance(
                    word=filler,
                    position=position,
                    timestamp=timestamp,
                    context=context,
                ))

                filler_counts[filler] = filler_counts.get(filler, 0) + 1

        analysis.filler_instances = instances
        analysis.filler_counts = filler_counts
        analysis.total_count = len(instances)

        # Calculate fillers per minute
        duration_minutes = (talk.metadata.duration_seconds or 0) / 60
        if duration_minutes > 0:
            analysis.fillers_per_minute = analysis.total_count / duration_minutes
        else:
            # Estimate from word count (average 150 WPM)
            estimated_minutes = talk.word_count / 150
            if estimated_minutes > 0:
                analysis.fillers_per_minute = analysis.total_count / estimated_minutes

        return analysis

    def analyze_pacing(self, talk: Talk) -> PacingAnalysis:
        """
        Analyze speaking pace across the talk.
        """
        analysis = PacingAnalysis()

        if not talk.segments:
            # If no segments, estimate from overall
            estimated_minutes = talk.word_count / 150  # Assume 150 WPM average
            if estimated_minutes > 0:
                analysis.average_wpm = talk.word_count / estimated_minutes
            return analysis

        # Analyze each segment
        total_words = 0
        total_duration = 0
        pacing_segments = []

        for segment in talk.segments:
            if segment.duration and segment.duration > 0:
                wpm = segment.words_per_minute
                if wpm:
                    level = self._classify_pacing(wpm)
                    pacing_segments.append(PacingSegment(
                        segment_index=segment.segment_index,
                        start_time=segment.start_time or 0,
                        end_time=segment.end_time or 0,
                        words_per_minute=wpm,
                        level=level,
                        word_count=segment.word_count,
                    ))

                    total_words += segment.word_count
                    total_duration += segment.duration

        analysis.segments = pacing_segments

        # Calculate overall average
        if total_duration > 0:
            analysis.average_wpm = (total_words / total_duration) * 60
            analysis.overall_level = self._classify_pacing(analysis.average_wpm)

        return analysis

    def _classify_pacing(self, wpm: float) -> PacingLevel:
        """Classify words-per-minute into a pacing level."""
        if wpm < self.config.pacing_slow_threshold - 20:
            return PacingLevel.VERY_SLOW
        elif wpm < self.config.pacing_slow_threshold:
            return PacingLevel.SLOW
        elif wpm <= self.config.pacing_fast_threshold:
            return PacingLevel.OPTIMAL
        elif wpm <= self.config.pacing_fast_threshold + 20:
            return PacingLevel.FAST
        else:
            return PacingLevel.RUSHED

    def analyze_pauses(self, talk: Talk) -> PauseAnalysis:
        """
        Detect significant pauses between segments.
        """
        analysis = PauseAnalysis()
        pauses = []

        if len(talk.segments) < 2:
            return analysis

        # Look for gaps between segments
        for i in range(len(talk.segments) - 1):
            current = talk.segments[i]
            next_seg = talk.segments[i + 1]

            if current.end_time is not None and next_seg.start_time is not None:
                gap = next_seg.start_time - current.end_time

                if gap >= self.config.pause_significant_threshold:
                    pauses.append(PauseInstance(
                        start_time=current.end_time,
                        end_time=next_seg.start_time,
                        preceding_text=current.text[-100:] if len(current.text) > 100 else current.text,
                        following_text=next_seg.text[:100] if len(next_seg.text) > 100 else next_seg.text,
                    ))

        analysis.pauses = pauses

        if pauses:
            analysis.total_pause_time = sum(p.duration for p in pauses)
            analysis.average_pause_duration = analysis.total_pause_time / len(pauses)

        return analysis

    def analyze_energy(self, talk: Talk) -> EnergyAnalysis:
        """
        Estimate energy levels throughout the talk using text heuristics.

        Note: This is a heuristic-based analysis since we only have text.
        More accurate analysis would require audio features.
        """
        analysis = EnergyAnalysis()

        # Energy indicators in text
        high_energy_patterns = [
            r'!+',                              # Exclamation marks
            r'\b(amazing|incredible|fantastic|awesome|exciting|powerful)\b',
            r'\b(absolutely|definitely|certainly|truly)\b',
            r'[A-Z]{3,}',                       # ALL CAPS words
        ]

        low_energy_patterns = [
            r'\.\.\.',                          # Trailing off
            r'\b(perhaps|maybe|might|could|possibly)\b',
            r'\b(um|uh|er|ah)\b',
        ]

        peak_patterns = [
            r'\b(most important|key point|remember this|crucial|essential)\b',
            r'\b(here\'s the thing|bottom line|the truth is)\b',
        ]

        timeline = []

        for segment in talk.segments:
            text = segment.text

            # Count indicators
            high_score = sum(
                len(re.findall(pattern, text, re.IGNORECASE))
                for pattern in high_energy_patterns
            )
            low_score = sum(
                len(re.findall(pattern, text, re.IGNORECASE))
                for pattern in low_energy_patterns
            )
            peak_indicators = sum(
                len(re.findall(pattern, text, re.IGNORECASE))
                for pattern in peak_patterns
            )

            # Determine energy level
            if peak_indicators > 0 or high_score > 3:
                level = EnergyLevel.PEAK
            elif high_score > low_score:
                level = EnergyLevel.HIGH
            elif low_score > high_score:
                level = EnergyLevel.LOW
            else:
                level = EnergyLevel.MODERATE

            indicators = []
            if high_score > 0:
                indicators.append(f"high_energy_words:{high_score}")
            if low_score > 0:
                indicators.append(f"low_energy_words:{low_score}")
            if peak_indicators > 0:
                indicators.append(f"peak_indicators:{peak_indicators}")

            if segment.start_time is not None:
                timeline.append(EnergyPoint(
                    timestamp=segment.start_time,
                    level=level,
                    context=segment.text[:50] + "..." if len(segment.text) > 50 else segment.text,
                    indicators=indicators,
                ))

        analysis.energy_timeline = timeline

        # Calculate average and find peaks/lows
        if timeline:
            level_values = {
                EnergyLevel.LOW: 1,
                EnergyLevel.MODERATE: 2,
                EnergyLevel.HIGH: 3,
                EnergyLevel.PEAK: 4,
            }
            avg_value = sum(level_values[p.level] for p in timeline) / len(timeline)

            if avg_value < 1.5:
                analysis.average_level = EnergyLevel.LOW
            elif avg_value < 2.5:
                analysis.average_level = EnergyLevel.MODERATE
            elif avg_value < 3.5:
                analysis.average_level = EnergyLevel.HIGH
            else:
                analysis.average_level = EnergyLevel.PEAK

            analysis.peak_moments = [p for p in timeline if p.level == EnergyLevel.PEAK]
            analysis.low_moments = [p for p in timeline if p.level == EnergyLevel.LOW]

        return analysis

    def detect_tone_shifts(self, talk: Talk) -> list[ToneShift]:
        """
        Detect shifts in tone throughout the talk.
        """
        tone_shifts = []

        # Tone patterns
        tone_patterns = {
            ToneType.ENTHUSIASTIC: [
                r'\b(love|excited|thrilled|amazing|fantastic|wonderful)\b',
                r'!{2,}',
            ],
            ToneType.SERIOUS: [
                r'\b(important|critical|serious|must|need to|have to)\b',
                r'\b(challenge|problem|issue|concern|risk)\b',
            ],
            ToneType.HUMOROUS: [
                r'\b(funny|joke|laugh|hilarious|kidding)\b',
                r'\(laughter\)',
                r'\[laughter\]',
            ],
            ToneType.REFLECTIVE: [
                r'\b(remember|think back|looking back|reflect|consider)\b',
                r'\b(learned|realized|discovered|understood)\b',
            ],
            ToneType.QUESTIONING: [
                r'\?{2,}',
                r'\b(why|how come|what if|wonder|curious)\b',
            ],
            ToneType.EMPHATIC: [
                r'\b(absolutely|definitely|without a doubt|certainly)\b',
                r'[A-Z]{4,}',
            ],
        }

        previous_tone = ToneType.NEUTRAL

        for segment in talk.segments:
            if segment.start_time is None:
                continue

            text = segment.text

            # Score each tone
            tone_scores = {}
            for tone, patterns in tone_patterns.items():
                score = sum(
                    len(re.findall(pattern, text, re.IGNORECASE))
                    for pattern in patterns
                )
                if score > 0:
                    tone_scores[tone] = score

            # Find dominant tone
            if tone_scores:
                current_tone = max(tone_scores, key=tone_scores.get)
            else:
                current_tone = ToneType.NEUTRAL

            # Record shift if different from previous
            if current_tone != previous_tone and current_tone != ToneType.NEUTRAL:
                tone_shifts.append(ToneShift(
                    timestamp=segment.start_time,
                    from_tone=previous_tone,
                    to_tone=current_tone,
                    context=segment.text[:80] + "..." if len(segment.text) > 80 else segment.text,
                ))
                previous_tone = current_tone

        return tone_shifts

    def _position_to_timestamp(self, talk: Talk, char_position: int) -> Optional[float]:
        """
        Estimate timestamp from character position in transcript.
        """
        if not talk.segments or not any(s.start_time is not None for s in talk.segments):
            return None

        # Find which segment contains this position
        current_position = 0
        for segment in talk.segments:
            segment_end_position = current_position + len(segment.text) + 1  # +1 for space

            if char_position < segment_end_position:
                # Found the segment
                if segment.start_time is not None and segment.end_time is not None:
                    # Interpolate within segment
                    segment_progress = (char_position - current_position) / max(1, len(segment.text))
                    return segment.start_time + (segment.duration or 0) * segment_progress
                return segment.start_time

            current_position = segment_end_position

        # Position is past all segments
        if talk.segments and talk.segments[-1].end_time is not None:
            return talk.segments[-1].end_time

        return None

    def get_delivery_summary(self, metrics: DeliveryMetrics) -> str:
        """
        Generate a human-readable summary of delivery analysis.
        """
        lines = []

        # Filler summary
        filler = metrics.filler_analysis
        lines.append(f"**Filler Words:** {filler.total_count} total ({filler.fillers_per_minute:.1f}/min)")
        lines.append(f"  Assessment: {filler.assessment}")
        if filler.most_common_filler:
            lines.append(f"  Most common: \"{filler.most_common_filler}\" ({filler.filler_counts.get(filler.most_common_filler, 0)}x)")

        lines.append("")

        # Pacing summary
        pacing = metrics.pacing_analysis
        lines.append(f"**Pacing:** {pacing.average_wpm:.0f} WPM average ({pacing.overall_level.value.replace('_', ' ')})")
        lines.append(f"  Consistency: {pacing.consistency_score:.0f}%")
        if pacing.rushed_segments:
            lines.append(f"  Rushed sections: {len(pacing.rushed_segments)}")
        if pacing.slow_segments:
            lines.append(f"  Slow sections: {len(pacing.slow_segments)}")

        lines.append("")

        # Pause summary
        pause = metrics.pause_analysis
        lines.append(f"**Pauses:** {len(pause.significant_pauses)} significant, {len(pause.dramatic_pauses)} dramatic")
        if pause.average_pause_duration > 0:
            lines.append(f"  Average duration: {pause.average_pause_duration:.1f}s")

        lines.append("")

        # Energy summary
        energy = metrics.energy_analysis
        lines.append(f"**Energy:** Average level is {energy.average_level.value}")
        lines.append(f"  Variation: {energy.energy_variation_score:.0f}%")
        if energy.peak_moments:
            lines.append(f"  Peak moments: {len(energy.peak_moments)}")

        lines.append("")

        # Tone summary
        if metrics.tone_shifts:
            lines.append(f"**Tone Shifts:** {len(metrics.tone_shifts)} detected")

        lines.append("")
        lines.append(f"**Overall Delivery Score:** {metrics.overall_delivery_score:.0f}/100")

        return "\n".join(lines)
