"""
Content analysis: quote extraction, theme detection, and key insights.
"""

import re
from typing import Optional
from collections import Counter

from ..models.talk import Talk
from ..models.quotes import Quote, QuoteCollection, QuoteCategory, QuoteQuality
from ..config import default_config, AnalyzerConfig


class ContentAnalyzer:
    """
    Analyze talk content for quotes, themes, and key insights.
    """

    def __init__(self, config: Optional[AnalyzerConfig] = None):
        self.config = config or default_config

    def extract_quotes(self, talk: Talk) -> QuoteCollection:
        """
        Extract notable quotes from a talk transcript.

        Uses heuristics to identify potentially quotable passages:
        - Definitive statements
        - Memorable phrases
        - Key insights
        - Calls to action
        """
        collection = QuoteCollection()

        # Split into sentences for analysis
        sentences = self._split_into_sentences(talk.raw_transcript)

        for i, sentence in enumerate(sentences):
            # Skip if too short or too long
            word_count = len(sentence.split())
            if word_count < self.config.quote_min_words or word_count > self.config.quote_max_words:
                continue

            # Score the sentence for quotability
            score, categories = self._score_quotability(sentence)

            if score >= 2:  # Minimum threshold for extraction
                # Get context
                context_before = sentences[i - 1] if i > 0 else ""
                context_after = sentences[i + 1] if i < len(sentences) - 1 else ""

                # Determine quality based on score
                if score >= 5:
                    quality = QuoteQuality.OUTSTANDING
                elif score >= 4:
                    quality = QuoteQuality.EXCELLENT
                elif score >= 3:
                    quality = QuoteQuality.GOOD
                else:
                    quality = QuoteQuality.FAIR

                # Find timestamp
                timestamp = self._find_timestamp_for_text(talk, sentence)

                quote = Quote(
                    text=sentence.strip(),
                    talk_id=talk.id,
                    timestamp=timestamp,
                    context_before=context_before,
                    context_after=context_after,
                    categories=categories,
                    quality=quality,
                )
                collection.add(quote)

        return collection

    def _score_quotability(self, sentence: str) -> tuple[int, list[QuoteCategory]]:
        """
        Score a sentence for quotability and identify categories.
        Returns (score, [categories]).
        """
        score = 0
        categories = []

        text = sentence.lower()

        # Inspiring patterns
        inspiring_patterns = [
            r'\b(transform|change the world|make a difference|possibility|potential)\b',
            r'\b(dream|vision|future|hope|believe|imagine)\b',
            r'\b(courage|brave|bold|fearless)\b',
        ]
        inspiring_score = sum(len(re.findall(p, text)) for p in inspiring_patterns)
        if inspiring_score > 0:
            score += inspiring_score
            categories.append(QuoteCategory.INSPIRING)

        # Insightful patterns
        insightful_patterns = [
            r'\b(realize|discover|understand|truth is|key is|secret is)\b',
            r'\b(insight|perspective|lens|framework|paradigm)\b',
            r'\b(actually|turns out|contrary to|counterintuitive)\b',
        ]
        insightful_score = sum(len(re.findall(p, text)) for p in insightful_patterns)
        if insightful_score > 0:
            score += insightful_score
            categories.append(QuoteCategory.INSIGHTFUL)

        # Practical patterns
        practical_patterns = [
            r'\b(step|action|start by|you can|try|implement)\b',
            r'\b(practical|concrete|specific|tangible|actionable)\b',
            r'\b(first|second|third|next|then)\b',
        ]
        practical_score = sum(len(re.findall(p, text)) for p in practical_patterns)
        if practical_score > 0:
            score += practical_score
            categories.append(QuoteCategory.PRACTICAL)

        # Memorable/quotable patterns (structure matters)
        memorable_patterns = [
            r'^the (best|only|most|real|true) .+ is',  # "The best X is Y"
            r'\bis not .+, it\'s',                      # "X is not Y, it's Z"
            r'\bif you .+, then',                       # Conditional wisdom
            r'\bthe more .+, the more',                 # Parallelism
            r'\b(never|always|every)\b',                # Absolute statements
        ]
        memorable_score = sum(len(re.findall(p, text)) for p in memorable_patterns)
        if memorable_score > 0:
            score += memorable_score * 2  # Weight structural patterns more
            categories.append(QuoteCategory.MEMORABLE)

        # Call to action patterns
        cta_patterns = [
            r'\b(go|do|make|create|build|start|begin|try)\b.+(today|now|tomorrow)',
            r'\b(challenge|urge|encourage|invite) (you|us)\b',
            r'\blet\'s\b',
            r'\byour (mission|task|job|goal)\b',
        ]
        cta_score = sum(len(re.findall(p, text)) for p in cta_patterns)
        if cta_score > 0:
            score += cta_score
            categories.append(QuoteCategory.CALL_TO_ACTION)

        # Provocative patterns
        provocative_patterns = [
            r'\?$',                                      # Ends with question
            r'\b(what if|imagine if|consider)\b',
            r'\b(wrong|mistake|myth|lie|misconception)\b',
        ]
        provocative_score = sum(len(re.findall(p, text)) for p in provocative_patterns)
        if provocative_score > 0:
            score += provocative_score
            categories.append(QuoteCategory.PROVOCATIVE)

        # Story indicators
        story_patterns = [
            r'\b(remember when|one day|there was|story|happened)\b',
            r'\b(he said|she said|I said|they said)\b',
            r'\b(walked|saw|felt|heard|realized)\b',
        ]
        story_score = sum(len(re.findall(p, text)) for p in story_patterns)
        if story_score >= 2:
            score += 1
            categories.append(QuoteCategory.STORY)

        # Statistics
        stat_patterns = [
            r'\d+%',
            r'\d+ (percent|times|x|fold)',
            r'\b(study|research|data|survey|statistics)\b',
        ]
        stat_score = sum(len(re.findall(p, text)) for p in stat_patterns)
        if stat_score > 0:
            score += stat_score
            categories.append(QuoteCategory.STATISTIC)

        # Bonus for conciseness (15-25 words is ideal)
        word_count = len(sentence.split())
        if 15 <= word_count <= 25:
            score += 1

        # Bonus for strong opening words
        strong_openers = ['the', 'you', 'we', 'when', 'if', 'every', 'true']
        first_word = text.split()[0] if text.split() else ""
        if first_word in strong_openers:
            score += 0.5

        # Default category if none matched
        if not categories and score >= 2:
            categories.append(QuoteCategory.QUOTABLE)

        return int(score), categories

    def extract_themes(self, talk: Talk, top_n: int = 10) -> list[tuple[str, int]]:
        """
        Extract main themes/topics from a talk.
        Returns list of (theme, frequency) tuples.
        """
        # Common words to exclude
        stop_words = {
            'the', 'a', 'an', 'and', 'or', 'but', 'in', 'on', 'at', 'to', 'for',
            'of', 'with', 'by', 'from', 'as', 'is', 'was', 'are', 'were', 'been',
            'be', 'have', 'has', 'had', 'do', 'does', 'did', 'will', 'would',
            'could', 'should', 'may', 'might', 'must', 'shall', 'can', 'need',
            'that', 'this', 'these', 'those', 'what', 'which', 'who', 'whom',
            'it', 'its', 'they', 'them', 'their', 'we', 'us', 'our', 'you', 'your',
            'i', 'me', 'my', 'he', 'him', 'his', 'she', 'her', 'so', 'if', 'then',
            'than', 'too', 'very', 'just', 'about', 'into', 'through', 'after',
            'before', 'above', 'below', 'up', 'down', 'out', 'off', 'over', 'under',
            'again', 'further', 'once', 'here', 'there', 'when', 'where', 'why',
            'how', 'all', 'each', 'every', 'both', 'few', 'more', 'most', 'other',
            'some', 'such', 'no', 'not', 'only', 'own', 'same', 'than', 'too',
            'very', 'just', 'because', 'while', 'during', 'right', 'now', 'going',
            'get', 'got', 'make', 'made', 'know', 'think', 'see', 'look', 'like',
            'want', 'say', 'said', 'really', 'actually', 'thing', 'things', 'way',
            'lot', 'kind', 'something', 'someone', 'people', 'time', 'well', 'even',
            'come', 'go', 'take', 'being', 'also', 'back', 'give', 'good', 'new',
        }

        text = talk.raw_transcript.lower()

        # Extract words (2+ characters, alphabetic)
        words = re.findall(r'\b[a-z]{3,}\b', text)

        # Filter stop words and count
        word_counts = Counter(
            word for word in words
            if word not in stop_words
        )

        # Also extract bigrams (two-word phrases)
        bigrams = []
        word_list = text.split()
        for i in range(len(word_list) - 1):
            w1 = re.sub(r'[^a-z]', '', word_list[i].lower())
            w2 = re.sub(r'[^a-z]', '', word_list[i + 1].lower())
            if w1 and w2 and w1 not in stop_words and w2 not in stop_words:
                if len(w1) >= 3 and len(w2) >= 3:
                    bigrams.append(f"{w1} {w2}")

        bigram_counts = Counter(bigrams)

        # Combine single words and phrases
        themes = []

        # Add top bigrams (they're often more meaningful)
        for phrase, count in bigram_counts.most_common(top_n):
            if count >= 3:  # Must appear at least 3 times
                themes.append((phrase, count))

        # Add top single words
        for word, count in word_counts.most_common(top_n * 2):
            if count >= 5:  # Higher threshold for single words
                # Don't add if it's already part of a top bigram
                if not any(word in theme[0] for theme in themes):
                    themes.append((word, count))

        # Sort by frequency and return top N
        themes.sort(key=lambda x: x[1], reverse=True)
        return themes[:top_n]

    def find_key_moments(self, talk: Talk) -> list[dict]:
        """
        Identify key moments in the talk (openings, transitions, conclusions).
        """
        moments = []

        if not talk.segments:
            return moments

        # Opening (first segment)
        if talk.segments:
            first_seg = talk.segments[0]
            moments.append({
                'type': 'opening',
                'timestamp': first_seg.start_time or 0,
                'text': first_seg.text[:200],
                'analysis': self._analyze_opening(first_seg.text),
            })

        # Find transitions
        transition_patterns = [
            r'\b(now let\'s|moving on|next|turning to|another point|speaking of)\b',
            r'\b(first|second|third|finally|lastly|in conclusion)\b',
            r'\b(but here\'s|here\'s the thing|the key is|important point)\b',
        ]

        for segment in talk.segments[1:-1]:  # Skip first and last
            text = segment.text.lower()
            for pattern in transition_patterns:
                if re.search(pattern, text):
                    moments.append({
                        'type': 'transition',
                        'timestamp': segment.start_time,
                        'text': segment.text[:150],
                        'pattern': pattern,
                    })
                    break

        # Conclusion (last few segments)
        if len(talk.segments) >= 2:
            last_seg = talk.segments[-1]
            moments.append({
                'type': 'conclusion',
                'timestamp': last_seg.start_time,
                'text': last_seg.text[:200],
                'analysis': self._analyze_conclusion(last_seg.text),
            })

        return moments

    def _analyze_opening(self, text: str) -> str:
        """Analyze the opening style."""
        text_lower = text.lower()

        if re.search(r'\b(story|happened|remember when)\b', text_lower):
            return "Story-based opening"
        elif re.search(r'\b(imagine|what if|picture)\b', text_lower):
            return "Imagination hook"
        elif re.search(r'\d+%|\b(study|research|data)\b', text_lower):
            return "Data-driven opening"
        elif '?' in text:
            return "Question-based opening"
        elif re.search(r'\b(thank|glad|happy|excited)\b', text_lower):
            return "Gratitude opening"
        else:
            return "Direct opening"

    def _analyze_conclusion(self, text: str) -> str:
        """Analyze the conclusion style."""
        text_lower = text.lower()

        if re.search(r'\b(remember|don\'t forget|key takeaway)\b', text_lower):
            return "Summary conclusion"
        elif re.search(r'\b(go|do|start|try|challenge you)\b', text_lower):
            return "Call-to-action conclusion"
        elif re.search(r'\b(thank|grateful|appreciate)\b', text_lower):
            return "Gratitude conclusion"
        elif '?' in text:
            return "Thought-provoking conclusion"
        elif re.search(r'\b(together|we can|us all)\b', text_lower):
            return "Unifying conclusion"
        else:
            return "Direct conclusion"

    def _split_into_sentences(self, text: str) -> list[str]:
        """Split text into sentences."""
        # Basic sentence splitting
        # Handle common abbreviations
        text = re.sub(r'Mr\.', 'Mr', text)
        text = re.sub(r'Mrs\.', 'Mrs', text)
        text = re.sub(r'Dr\.', 'Dr', text)
        text = re.sub(r'vs\.', 'vs', text)
        text = re.sub(r'etc\.', 'etc', text)
        text = re.sub(r'i\.e\.', 'ie', text)
        text = re.sub(r'e\.g\.', 'eg', text)

        # Split on sentence boundaries
        sentences = re.split(r'(?<=[.!?])\s+', text)

        # Clean up
        return [s.strip() for s in sentences if s.strip()]

    def _find_timestamp_for_text(self, talk: Talk, target_text: str) -> Optional[float]:
        """Find the timestamp where a piece of text appears."""
        if not talk.segments:
            return None

        target_lower = target_text.lower()[:50]  # First 50 chars

        for segment in talk.segments:
            if target_lower in segment.text.lower():
                return segment.start_time

        return None

    def get_content_summary(self, talk: Talk, quotes: QuoteCollection, themes: list[tuple[str, int]]) -> str:
        """Generate a content analysis summary."""
        lines = []

        # Themes
        lines.append("**Main Themes:**")
        for theme, count in themes[:5]:
            lines.append(f"  - {theme} ({count} mentions)")

        lines.append("")

        # Quote statistics
        stats = quotes.get_statistics()
        lines.append(f"**Quotes Extracted:** {stats['total']}")
        if stats.get('by_quality'):
            lines.append("  By quality:")
            for quality, count in stats['by_quality'].items():
                lines.append(f"    - {quality}: {count}")

        lines.append("")

        if stats.get('by_category'):
            lines.append("  By category:")
            for category, count in stats['by_category'].items():
                lines.append(f"    - {category.replace('_', ' ')}: {count}")

        return "\n".join(lines)
