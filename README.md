# Talk Transcript Analyzer

A comprehensive Python tool for analyzing talk transcripts, extracting insights, tracking delivery metrics, and generating after-action review (AAR) artifacts.

## Features

### Delivery Analysis
- **Pacing Analysis** - Words per minute tracking, rushed/slow section detection
- **Filler Word Detection** - Track "um", "uh", "like", "you know", etc.
- **Pause Analysis** - Identify significant and dramatic pauses
- **Energy Level Tracking** - Estimate energy changes throughout the talk
- **Tone Shift Detection** - Identify changes in tone (enthusiastic, serious, etc.)

### Content Analysis
- **Quote Extraction** - Automatically identify quotable moments
- **Quality Scoring** - Rate quotes as Outstanding, Excellent, Good, or Fair
- **Category Tagging** - Tag quotes as inspiring, insightful, practical, etc.
- **Theme Extraction** - Identify recurring themes and topics

### Cross-Talk Intelligence
- **Trend Analysis** - Track delivery improvements over time
- **Topic Frequency** - See which topics you discuss most often
- **Talk Connections** - Find thematic links between talks
- **Audience Patterns** - Analyze performance by audience type

### Integrations
- **Email** - Send AARs via SMTP or SendGrid
- **Notion** - Sync quotes and summaries to Notion databases
- **Webhooks** - Connect to Slack, Discord, Zapier, and custom workflows

## Installation

```bash
# Clone the repository
git clone https://github.com/busterlarue/busterlarue.git
cd busterlarue

# Install in development mode
pip install -e .

# Or with optional dependencies
pip install -e ".[all]"
```

## Quick Start

### Analyze a Transcript

```bash
# Basic analysis
python -m talk_analyzer analyze transcript.txt --title "My Amazing Talk"

# With full metadata
python -m talk_analyzer analyze talk.srt \
    --title "AI in the Enterprise" \
    --date 2024-01-15 \
    --venue "Tech Conference 2024" \
    --topic "Artificial Intelligence" \
    --audience corporate \
    --audience-size 200 \
    --tags "ai,enterprise,strategy"
```

### View Your Talks

```bash
# List all talks
python -m talk_analyzer list

# Show talk details
python -m talk_analyzer show <talk-id>

# View database statistics
python -m talk_analyzer stats
```

### Work with Quotes

```bash
# List all quotes
python -m talk_analyzer quotes --list

# Show only outstanding quotes
python -m talk_analyzer quotes --outstanding

# Show favorites
python -m talk_analyzer quotes --favorites

# Search quotes
python -m talk_analyzer quotes --search "innovation"

# Export quotes to markdown
python -m talk_analyzer quotes --export quotes.md
```

### Analyze Trends

```bash
# View trend analysis
python -m talk_analyzer trends

# Compare two talks
python -m talk_analyzer compare <talk1-id> <talk2-id>
```

## Supported Transcript Formats

| Format | Extension | Timing Info |
|--------|-----------|-------------|
| Plain Text | `.txt` | No |
| SubRip Subtitles | `.srt` | Yes |
| WebVTT | `.vtt` | Yes |
| JSON | `.json` | Optional |

## After Action Review (AAR) Output

The AAR artifact includes:

```markdown
# After Action Review: [Talk Title]

## Executive Summary
- Overall delivery score
- Key themes
- Quote highlights

## Delivery Analysis
### Pacing
### Vocal Fillers
### Pauses
### Energy & Tone

## Outstanding Quotes
> "Your best quotes highlighted here"

## Key Themes
## Key Moments
## Action Items
```

## Python API

```python
from talk_analyzer import Talk, TranscriptParser
from talk_analyzer.analyzers import DeliveryAnalyzer, ContentAnalyzer
from talk_analyzer.artifacts import AfterActionReview

# Parse a transcript
talk = TranscriptParser.parse_file("talk.srt", title="My Talk")

# Analyze delivery
analyzer = DeliveryAnalyzer()
metrics = analyzer.analyze(talk)
print(f"Delivery Score: {metrics.overall_delivery_score}")

# Extract quotes
content = ContentAnalyzer()
quotes = content.extract_quotes(talk)
for quote in quotes.outstanding_quotes:
    print(f"Outstanding: {quote.text}")

# Generate AAR
aar = AfterActionReview()
report = aar.generate(talk, metrics, quotes)
print(report)
```

## Configuration

Set environment variables for integrations:

```bash
# Email (SendGrid)
export SENDGRID_API_KEY=your-key
export EMAIL_FROM=you@example.com

# Email (SMTP)
export SMTP_HOST=smtp.gmail.com
export SMTP_PORT=587
export SMTP_USER=you@gmail.com
export SMTP_PASSWORD=your-password

# Notion
export NOTION_API_KEY=your-key
export NOTION_DATABASE_ID=your-database-id
```

## Project Structure

```
talk_analyzer/
├── models/          # Data models (Talk, Quote, Metrics)
├── analyzers/       # Analysis engines
├── parsers/         # Transcript parsing
├── storage/         # SQLite database
├── artifacts/       # AAR generation
├── integrations/    # Email, Notion, Webhooks
└── cli.py           # Command-line interface
```

## License

MIT

---

*Built with Python 3.10+. No external dependencies required for core functionality.*
