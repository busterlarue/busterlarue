#!/usr/bin/env python3
"""
Command-line interface for the Talk Transcript Analyzer.

Usage:
    python -m talk_analyzer analyze transcript.txt --title "My Talk"
    python -m talk_analyzer quotes --list
    python -m talk_analyzer trends
"""

import argparse
import sys
from datetime import datetime
from pathlib import Path

from .models.talk import AudienceType
from .parsers.transcript import TranscriptParser
from .analyzers.delivery import DeliveryAnalyzer
from .analyzers.content import ContentAnalyzer
from .analyzers.trends import TrendAnalyzer
from .artifacts.aar import AfterActionReview
from .storage.database import Database
from .storage.export import Exporter
from .config import default_config


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="talk_analyzer",
        description="Analyze talk transcripts and generate after-action reviews",
    )

    parser.add_argument(
        "--db",
        type=str,
        default="./talk_analyzer.db",
        help="Path to database file (default: ./talk_analyzer.db)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Analyze command
    analyze = subparsers.add_parser("analyze", help="Analyze a transcript")
    analyze.add_argument("transcript", type=str, help="Path to transcript file")
    analyze.add_argument("--title", type=str, required=True, help="Talk title")
    analyze.add_argument("--date", type=str, help="Talk date (YYYY-MM-DD)")
    analyze.add_argument("--venue", type=str, help="Venue name")
    analyze.add_argument("--topic", type=str, help="Talk topic")
    analyze.add_argument(
        "--audience",
        type=str,
        choices=[a.value for a in AudienceType],
        help="Audience type",
    )
    analyze.add_argument("--audience-size", type=int, help="Number of attendees")
    analyze.add_argument("--tags", type=str, help="Comma-separated tags")
    analyze.add_argument(
        "--export-dir",
        type=str,
        default="./exports",
        help="Directory for exported files",
    )
    analyze.add_argument(
        "--no-save",
        action="store_true",
        help="Don't save to database",
    )

    # List talks command
    list_talks = subparsers.add_parser("list", help="List all talks")
    list_talks.add_argument("--limit", type=int, default=20, help="Number of talks to show")

    # Show talk command
    show = subparsers.add_parser("show", help="Show details of a talk")
    show.add_argument("talk_id", type=str, help="Talk ID")

    # Quotes command
    quotes = subparsers.add_parser("quotes", help="Manage quotes")
    quotes.add_argument("--list", action="store_true", help="List all quotes")
    quotes.add_argument("--favorites", action="store_true", help="Show favorites only")
    quotes.add_argument("--outstanding", action="store_true", help="Show outstanding only")
    quotes.add_argument("--talk", type=str, help="Show quotes from specific talk")
    quotes.add_argument("--search", type=str, help="Search quotes by text")
    quotes.add_argument("--export", type=str, help="Export quotes to file")

    # Trends command
    trends = subparsers.add_parser("trends", help="Analyze trends across talks")
    trends.add_argument("--export", type=str, help="Export trends report to file")

    # Compare command
    compare = subparsers.add_parser("compare", help="Compare two talks")
    compare.add_argument("talk1_id", type=str, help="First talk ID")
    compare.add_argument("talk2_id", type=str, help="Second talk ID")

    # Stats command
    subparsers.add_parser("stats", help="Show database statistics")

    # Export command
    export = subparsers.add_parser("export", help="Export data")
    export.add_argument("--talk", type=str, help="Export specific talk")
    export.add_argument("--all-quotes", action="store_true", help="Export all quotes")
    export.add_argument("--metrics-csv", action="store_true", help="Export metrics as CSV")
    export.add_argument("--dir", type=str, default="./exports", help="Export directory")

    return parser


def cmd_analyze(args, db: Database):
    """Analyze a transcript and generate AAR."""
    print(f"Analyzing: {args.transcript}")

    # Parse date
    talk_date = datetime.now()
    if args.date:
        try:
            talk_date = datetime.strptime(args.date, "%Y-%m-%d")
        except ValueError:
            print(f"Warning: Invalid date format '{args.date}', using today")

    # Parse audience type
    audience_type = AudienceType.OTHER
    if args.audience:
        audience_type = AudienceType(args.audience)

    # Parse tags
    tags = []
    if args.tags:
        tags = [t.strip() for t in args.tags.split(",")]

    # Parse transcript
    print("  Parsing transcript...")
    talk = TranscriptParser.parse_file(
        args.transcript,
        title=args.title,
        date=talk_date,
        venue=args.venue,
        topic=args.topic,
        audience_type=audience_type,
        audience_size=args.audience_size,
        tags=tags,
    )
    print(f"  Parsed {talk.word_count} words in {len(talk.segments)} segments")

    # Run delivery analysis
    print("  Analyzing delivery...")
    delivery_analyzer = DeliveryAnalyzer()
    metrics = delivery_analyzer.analyze(talk)
    print(f"  Delivery score: {metrics.overall_delivery_score:.0f}/100")

    # Extract quotes
    print("  Extracting quotes...")
    content_analyzer = ContentAnalyzer()
    quotes = content_analyzer.extract_quotes(talk)
    print(f"  Found {len(quotes.quotes)} quotes ({len(quotes.outstanding_quotes)} outstanding)")

    # Generate AAR
    print("  Generating After Action Review...")
    aar = AfterActionReview(database=db)
    aar_content = aar.generate(talk, metrics, quotes)

    # Save to database
    if not args.no_save:
        print("  Saving to database...")
        db.save_talk(talk)
        db.save_quotes(quotes.quotes)
        db.save_delivery_metrics(metrics)

    # Export
    exporter = Exporter(args.export_dir)
    exports = exporter.export_all(talk, quotes, metrics, aar_content)

    print(f"\nAnalysis complete!")
    print(f"\nExported files:")
    for name, path in exports.items():
        print(f"  - {name}: {path}")

    print(f"\n--- DELIVERY SUMMARY ---")
    print(delivery_analyzer.get_delivery_summary(metrics))


def cmd_list(args, db: Database):
    """List all talks."""
    talks = db.get_all_talks(limit=args.limit)

    if not talks:
        print("No talks found in database.")
        return

    print(f"{'ID':<36} {'Date':<12} {'Title':<40}")
    print("-" * 90)

    for talk in talks:
        date_str = talk.metadata.date.strftime("%Y-%m-%d")
        title = talk.metadata.title[:38] + ".." if len(talk.metadata.title) > 40 else talk.metadata.title
        print(f"{talk.id:<36} {date_str:<12} {title:<40}")


def cmd_show(args, db: Database):
    """Show details of a talk."""
    talk = db.get_talk(args.talk_id)

    if not talk:
        print(f"Talk not found: {args.talk_id}")
        return

    print(f"Title: {talk.metadata.title}")
    print(f"ID: {talk.id}")
    print(f"Date: {talk.metadata.date.strftime('%Y-%m-%d')}")
    print(f"Venue: {talk.metadata.venue or 'N/A'}")
    print(f"Topic: {talk.metadata.topic or 'N/A'}")
    print(f"Audience: {talk.metadata.audience_type.value}")
    print(f"Duration: {talk.metadata.duration_formatted}")
    print(f"Word Count: {talk.word_count}")
    print(f"Segments: {len(talk.segments)}")

    if talk.metadata.tags:
        print(f"Tags: {', '.join(talk.metadata.tags)}")

    # Show metrics if available
    metrics = db.get_delivery_metrics(talk.id)
    if metrics:
        print(f"\nDelivery Score: {metrics.get('overall_score', 'N/A')}")
        filler = metrics.get('filler_analysis', {})
        print(f"Fillers: {filler.get('total_count', 0)} ({filler.get('fillers_per_minute', 0):.1f}/min)")

    # Show quote count
    quotes = db.get_quotes_for_talk(talk.id)
    print(f"\nQuotes: {len(quotes.quotes)} extracted")


def cmd_quotes(args, db: Database):
    """Manage and view quotes."""
    if args.favorites:
        quotes = db.get_favorite_quotes()
        print(f"Favorite Quotes ({len(quotes.quotes)}):\n")
    elif args.outstanding:
        quotes = db.get_outstanding_quotes()
        print(f"Outstanding Quotes ({len(quotes.quotes)}):\n")
    elif args.talk:
        quotes = db.get_quotes_for_talk(args.talk)
        print(f"Quotes from talk ({len(quotes.quotes)}):\n")
    elif args.search:
        quotes = db.search_quotes(args.search)
        print(f"Search results for '{args.search}' ({len(quotes.quotes)}):\n")
    else:
        quotes = db.get_all_quotes()
        print(f"All Quotes ({len(quotes.quotes)}):\n")

    for quote in quotes.quotes[:20]:
        quality = quote.quality.value.upper()
        print(f"[{quality}] \"{quote.text}\"")
        if quote.timestamp_formatted:
            print(f"         @{quote.timestamp_formatted}")
        if quote.categories:
            print(f"         Tags: {', '.join(c.value for c in quote.categories)}")
        print()

    if args.export:
        exporter = Exporter()
        path = exporter.export_quotes_markdown(quotes, args.export)
        print(f"\nExported to: {path}")


def cmd_trends(args, db: Database):
    """Analyze and show trends."""
    analyzer = TrendAnalyzer(db)
    trends = analyzer.analyze_trends()

    summary = analyzer.get_trend_summary(trends)
    print(summary)

    if args.export:
        Path(args.export).write_text(summary)
        print(f"\nExported to: {args.export}")


def cmd_compare(args, db: Database):
    """Compare two talks."""
    talk1 = db.get_talk(args.talk1_id)
    talk2 = db.get_talk(args.talk2_id)

    if not talk1:
        print(f"Talk not found: {args.talk1_id}")
        return
    if not talk2:
        print(f"Talk not found: {args.talk2_id}")
        return

    aar = AfterActionReview(database=db)
    report = aar.generate_comparison_report(talk1, talk2)
    print(report)


def cmd_stats(args, db: Database):
    """Show database statistics."""
    stats = db.get_statistics()

    print("Database Statistics")
    print("-" * 40)
    print(f"Total Talks: {stats['total_talks']}")
    print(f"Total Quotes: {stats['total_quotes']}")
    print(f"Favorite Quotes: {stats['favorite_quotes']}")
    print(f"Average Delivery Score: {stats['average_delivery_score']:.1f}")

    if stats['first_talk_date']:
        print(f"First Talk: {stats['first_talk_date']}")
    if stats['last_talk_date']:
        print(f"Last Talk: {stats['last_talk_date']}")


def cmd_export(args, db: Database):
    """Export data."""
    exporter = Exporter(args.dir)

    if args.talk:
        talk = db.get_talk(args.talk)
        if not talk:
            print(f"Talk not found: {args.talk}")
            return
        path = exporter.export_talk_json(talk)
        print(f"Exported talk to: {path}")

    if args.all_quotes:
        quotes = db.get_all_quotes()
        path = exporter.export_quotes_markdown(quotes)
        print(f"Exported quotes to: {path}")

    if args.metrics_csv:
        history = db.get_metrics_history()
        path = exporter.export_metrics_csv(history)
        print(f"Exported metrics to: {path}")


def main():
    """Main entry point."""
    parser = create_parser()
    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(0)

    # Initialize database
    db = Database(args.db)

    # Route to command handler
    commands = {
        "analyze": cmd_analyze,
        "list": cmd_list,
        "show": cmd_show,
        "quotes": cmd_quotes,
        "trends": cmd_trends,
        "compare": cmd_compare,
        "stats": cmd_stats,
        "export": cmd_export,
    }

    handler = commands.get(args.command)
    if handler:
        handler(args, db)
    else:
        parser.print_help()


if __name__ == "__main__":
    main()
