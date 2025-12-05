"""
Transcript parser supporting multiple formats.

Supports:
- Plain text (.txt)
- SubRip subtitles (.srt)
- WebVTT subtitles (.vtt)
- JSON with timestamps
"""

import re
from pathlib import Path
from datetime import datetime
from typing import Optional
import json

from ..models.talk import Talk, TalkMetadata, Segment, AudienceType


class TranscriptParser:
    """
    Parse transcripts from various formats into Talk objects.
    """

    @classmethod
    def parse_file(
        cls,
        file_path: str | Path,
        title: Optional[str] = None,
        date: Optional[datetime] = None,
        **metadata_kwargs
    ) -> Talk:
        """
        Parse a transcript file into a Talk object.
        Automatically detects format based on file extension.
        """
        path = Path(file_path)
        content = path.read_text(encoding="utf-8")

        extension = path.suffix.lower()

        if extension == ".srt":
            return cls.parse_srt(content, title or path.stem, date, **metadata_kwargs)
        elif extension == ".vtt":
            return cls.parse_vtt(content, title or path.stem, date, **metadata_kwargs)
        elif extension == ".json":
            return cls.parse_json(content, title, date, **metadata_kwargs)
        else:
            # Default to plain text
            return cls.parse_text(content, title or path.stem, date, **metadata_kwargs)

    @classmethod
    def parse_text(
        cls,
        content: str,
        title: str = "Untitled Talk",
        date: Optional[datetime] = None,
        **metadata_kwargs
    ) -> Talk:
        """
        Parse plain text transcript (no timing information).
        """
        # Clean up the text
        text = content.strip()

        # Create segments by paragraph
        paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

        segments = []
        for i, para in enumerate(paragraphs):
            # Combine lines within a paragraph
            clean_para = " ".join(line.strip() for line in para.split("\n") if line.strip())
            if clean_para:
                segments.append(Segment(
                    text=clean_para,
                    start_time=None,
                    end_time=None,
                    segment_index=i,
                ))

        metadata = TalkMetadata(
            title=title,
            date=date or datetime.now(),
            **{k: v for k, v in metadata_kwargs.items() if v is not None}
        )

        return Talk(
            metadata=metadata,
            raw_transcript=text,
            segments=segments,
        )

    @classmethod
    def parse_srt(
        cls,
        content: str,
        title: str = "Untitled Talk",
        date: Optional[datetime] = None,
        **metadata_kwargs
    ) -> Talk:
        """
        Parse SRT (SubRip) subtitle format.

        Format:
        1
        00:00:00,000 --> 00:00:04,000
        Text here

        2
        00:00:04,000 --> 00:00:08,000
        More text
        """
        segments = []
        raw_text_parts = []

        # SRT pattern: index, timestamp line, text, blank line
        pattern = re.compile(
            r'(\d+)\s*\n'                           # Index
            r'(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*-->\s*'  # Start time
            r'(\d{2}:\d{2}:\d{2}[,\.]\d{3})\s*\n'     # End time
            r'((?:(?!\n\n|\n\d+\n).)+)',              # Text (until blank line or next index)
            re.DOTALL
        )

        for match in pattern.finditer(content):
            index = int(match.group(1))
            start_time = cls._parse_srt_timestamp(match.group(2))
            end_time = cls._parse_srt_timestamp(match.group(3))
            text = match.group(4).strip().replace("\n", " ")

            # Remove any HTML-style tags (common in subtitles)
            text = re.sub(r'<[^>]+>', '', text)

            if text:
                segments.append(Segment(
                    text=text,
                    start_time=start_time,
                    end_time=end_time,
                    segment_index=index - 1,
                ))
                raw_text_parts.append(text)

        raw_transcript = " ".join(raw_text_parts)

        # Calculate total duration
        duration = None
        if segments and segments[-1].end_time:
            duration = segments[-1].end_time

        metadata = TalkMetadata(
            title=title,
            date=date or datetime.now(),
            duration_seconds=duration,
            **{k: v for k, v in metadata_kwargs.items() if v is not None}
        )

        return Talk(
            metadata=metadata,
            raw_transcript=raw_transcript,
            segments=segments,
        )

    @classmethod
    def parse_vtt(
        cls,
        content: str,
        title: str = "Untitled Talk",
        date: Optional[datetime] = None,
        **metadata_kwargs
    ) -> Talk:
        """
        Parse WebVTT subtitle format.

        Format:
        WEBVTT

        00:00:00.000 --> 00:00:04.000
        Text here

        00:00:04.000 --> 00:00:08.000
        More text
        """
        segments = []
        raw_text_parts = []

        # Skip the WEBVTT header and any metadata
        lines = content.split("\n")
        start_idx = 0
        for i, line in enumerate(lines):
            if line.strip() == "WEBVTT" or line.startswith("NOTE") or line.strip() == "":
                start_idx = i + 1
            elif "-->" in line:
                start_idx = i
                break

        content_after_header = "\n".join(lines[start_idx:])

        # VTT pattern: optional cue id, timestamp line, text
        pattern = re.compile(
            r'(?:^|\n\n)'                            # Start of content or blank line
            r'(?:([^\n]+)\n)?'                       # Optional cue identifier
            r'(\d{2}:\d{2}:\d{2}\.\d{3})\s*-->\s*'   # Start time
            r'(\d{2}:\d{2}:\d{2}\.\d{3})'            # End time
            r'(?:[^\n]*)?\n'                         # Optional cue settings
            r'((?:(?!\n\n).)+)',                     # Text (until blank line)
            re.DOTALL
        )

        segment_index = 0
        for match in pattern.finditer(content_after_header):
            start_time = cls._parse_vtt_timestamp(match.group(2))
            end_time = cls._parse_vtt_timestamp(match.group(3))
            text = match.group(4).strip().replace("\n", " ")

            # Remove VTT styling tags
            text = re.sub(r'<[^>]+>', '', text)
            text = re.sub(r'\{[^}]+\}', '', text)

            if text:
                segments.append(Segment(
                    text=text,
                    start_time=start_time,
                    end_time=end_time,
                    segment_index=segment_index,
                ))
                raw_text_parts.append(text)
                segment_index += 1

        raw_transcript = " ".join(raw_text_parts)

        # Calculate total duration
        duration = None
        if segments and segments[-1].end_time:
            duration = segments[-1].end_time

        metadata = TalkMetadata(
            title=title,
            date=date or datetime.now(),
            duration_seconds=duration,
            **{k: v for k, v in metadata_kwargs.items() if v is not None}
        )

        return Talk(
            metadata=metadata,
            raw_transcript=raw_transcript,
            segments=segments,
        )

    @classmethod
    def parse_json(
        cls,
        content: str,
        title: Optional[str] = None,
        date: Optional[datetime] = None,
        **metadata_kwargs
    ) -> Talk:
        """
        Parse JSON transcript format.

        Expected format:
        {
            "title": "Talk Title",
            "date": "2024-01-15",
            "segments": [
                {"text": "Hello everyone", "start": 0.0, "end": 2.5},
                {"text": "Welcome to this talk", "start": 2.5, "end": 5.0}
            ]
        }

        Or simple format:
        {
            "transcript": "Full transcript text here..."
        }
        """
        data = json.loads(content)

        # Handle different JSON structures
        if "segments" in data:
            segments = []
            raw_text_parts = []

            for i, seg in enumerate(data["segments"]):
                text = seg.get("text", "").strip()
                if text:
                    segments.append(Segment(
                        text=text,
                        start_time=seg.get("start") or seg.get("start_time"),
                        end_time=seg.get("end") or seg.get("end_time"),
                        segment_index=i,
                    ))
                    raw_text_parts.append(text)

            raw_transcript = " ".join(raw_text_parts)
            duration = segments[-1].end_time if segments and segments[-1].end_time else None

        elif "transcript" in data:
            raw_transcript = data["transcript"]
            segments = [Segment(text=raw_transcript, segment_index=0)]
            duration = data.get("duration") or data.get("duration_seconds")

        elif "text" in data:
            raw_transcript = data["text"]
            segments = [Segment(text=raw_transcript, segment_index=0)]
            duration = data.get("duration") or data.get("duration_seconds")

        else:
            raise ValueError("JSON must contain 'segments', 'transcript', or 'text' field")

        # Extract metadata from JSON
        json_title = data.get("title") or title or "Untitled Talk"
        json_date = date
        if not json_date and data.get("date"):
            try:
                json_date = datetime.fromisoformat(data["date"])
            except (ValueError, TypeError):
                json_date = datetime.now()

        # Merge metadata from JSON and kwargs
        meta_dict = {
            "venue": data.get("venue"),
            "topic": data.get("topic"),
            "audience_size": data.get("audience_size"),
            "duration_seconds": duration,
            "tags": data.get("tags", []),
            "notes": data.get("notes"),
        }

        # Handle audience_type
        if data.get("audience_type"):
            try:
                meta_dict["audience_type"] = AudienceType(data["audience_type"])
            except ValueError:
                meta_dict["audience_type"] = AudienceType.OTHER

        # Kwargs override JSON values
        meta_dict.update({k: v for k, v in metadata_kwargs.items() if v is not None})

        metadata = TalkMetadata(
            title=json_title,
            date=json_date or datetime.now(),
            **{k: v for k, v in meta_dict.items() if v is not None}
        )

        return Talk(
            metadata=metadata,
            raw_transcript=raw_transcript,
            segments=segments,
        )

    @staticmethod
    def _parse_srt_timestamp(timestamp: str) -> float:
        """Parse SRT timestamp (HH:MM:SS,mmm) to seconds."""
        # Handle both comma and period as decimal separator
        timestamp = timestamp.replace(",", ".")
        parts = timestamp.split(":")
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds

    @staticmethod
    def _parse_vtt_timestamp(timestamp: str) -> float:
        """Parse VTT timestamp (HH:MM:SS.mmm) to seconds."""
        parts = timestamp.split(":")
        hours = int(parts[0])
        minutes = int(parts[1])
        seconds = float(parts[2])
        return hours * 3600 + minutes * 60 + seconds

    @classmethod
    def merge_short_segments(cls, talk: Talk, min_duration: float = 5.0) -> Talk:
        """
        Merge very short segments together for better analysis.
        Useful when subtitle segments are very fragmented.
        """
        if not talk.segments or len(talk.segments) < 2:
            return talk

        merged = []
        current_texts = []
        current_start = None
        current_end = None

        for segment in talk.segments:
            if current_start is None:
                current_start = segment.start_time
                current_texts = [segment.text]
                current_end = segment.end_time
            else:
                duration = (current_end or 0) - (current_start or 0) if current_start else 0
                if duration < min_duration:
                    # Merge with current
                    current_texts.append(segment.text)
                    current_end = segment.end_time
                else:
                    # Save current and start new
                    merged.append(Segment(
                        text=" ".join(current_texts),
                        start_time=current_start,
                        end_time=current_end,
                        segment_index=len(merged),
                    ))
                    current_start = segment.start_time
                    current_texts = [segment.text]
                    current_end = segment.end_time

        # Don't forget the last segment
        if current_texts:
            merged.append(Segment(
                text=" ".join(current_texts),
                start_time=current_start,
                end_time=current_end,
                segment_index=len(merged),
            ))

        talk.segments = merged
        return talk

    @classmethod
    def segment_by_duration(cls, talk: Talk, segment_duration: float = 60.0) -> Talk:
        """
        Re-segment a talk into fixed-duration segments for consistent analysis.
        """
        if not talk.segments:
            return talk

        # If no timing info, just return as-is
        if not any(s.start_time is not None for s in talk.segments):
            return talk

        new_segments = []
        current_segment_text = []
        current_segment_start = 0.0
        segment_index = 0

        for segment in talk.segments:
            if segment.start_time is None:
                continue

            # Check if we've crossed a segment boundary
            while segment.start_time >= current_segment_start + segment_duration:
                if current_segment_text:
                    new_segments.append(Segment(
                        text=" ".join(current_segment_text),
                        start_time=current_segment_start,
                        end_time=current_segment_start + segment_duration,
                        segment_index=segment_index,
                    ))
                    segment_index += 1
                    current_segment_text = []
                current_segment_start += segment_duration

            current_segment_text.append(segment.text)

        # Add final segment
        if current_segment_text:
            final_end = talk.segments[-1].end_time if talk.segments[-1].end_time else current_segment_start + segment_duration
            new_segments.append(Segment(
                text=" ".join(current_segment_text),
                start_time=current_segment_start,
                end_time=final_end,
                segment_index=segment_index,
            ))

        talk.segments = new_segments
        return talk
