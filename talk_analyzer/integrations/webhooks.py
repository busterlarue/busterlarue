"""
Webhook integration for custom workflows.

Send analysis results to external services via HTTP.
"""

import json
from typing import Optional, Any
from urllib.request import Request, urlopen
from urllib.error import URLError, HTTPError
from datetime import datetime

from ..models.talk import Talk
from ..models.quotes import Quote, QuoteCollection
from ..models.delivery import DeliveryMetrics


class WebhookSender:
    """
    Send webhook notifications for talk analysis events.
    """

    def __init__(
        self,
        webhook_url: str,
        headers: Optional[dict[str, str]] = None,
        timeout: int = 30,
    ):
        """
        Initialize webhook sender.

        Args:
            webhook_url: The URL to send webhooks to
            headers: Optional custom headers (e.g., authorization)
            timeout: Request timeout in seconds
        """
        self.webhook_url = webhook_url
        self.headers = headers or {}
        self.timeout = timeout

        # Default headers
        if "Content-Type" not in self.headers:
            self.headers["Content-Type"] = "application/json"

    def send(self, payload: dict[str, Any]) -> tuple[bool, str]:
        """
        Send a webhook payload.

        Returns:
            Tuple of (success, response_or_error)
        """
        try:
            data = json.dumps(payload, default=str).encode("utf-8")
            request = Request(
                self.webhook_url,
                data=data,
                headers=self.headers,
                method="POST",
            )

            with urlopen(request, timeout=self.timeout) as response:
                body = response.read().decode("utf-8")
                return True, body

        except HTTPError as e:
            return False, f"HTTP {e.code}: {e.reason}"
        except URLError as e:
            return False, f"URL Error: {e.reason}"
        except Exception as e:
            return False, str(e)

    def send_analysis_complete(
        self,
        talk: Talk,
        metrics: DeliveryMetrics,
        quotes: QuoteCollection,
        aar_content: Optional[str] = None,
    ) -> tuple[bool, str]:
        """
        Send notification that analysis is complete.
        """
        payload = {
            "event": "analysis_complete",
            "timestamp": datetime.now().isoformat(),
            "talk": {
                "id": talk.id,
                "title": talk.metadata.title,
                "date": talk.metadata.date.isoformat(),
                "venue": talk.metadata.venue,
                "topic": talk.metadata.topic,
                "word_count": talk.word_count,
                "duration": talk.metadata.duration_seconds,
            },
            "metrics": {
                "delivery_score": metrics.overall_delivery_score,
                "filler_count": metrics.filler_analysis.total_count,
                "fillers_per_minute": round(metrics.filler_analysis.fillers_per_minute, 2),
                "average_wpm": round(metrics.pacing_analysis.average_wpm, 1),
                "pacing_level": metrics.pacing_analysis.overall_level.value,
            },
            "quotes": {
                "total_extracted": len(quotes.quotes),
                "outstanding": len(quotes.outstanding_quotes),
                "categories": quotes.get_statistics().get("by_category", {}),
            },
        }

        if aar_content:
            # Include truncated AAR for webhooks
            payload["aar_preview"] = aar_content[:2000] + "..." if len(aar_content) > 2000 else aar_content

        return self.send(payload)

    def send_quote_extracted(self, quote: Quote, talk_title: str = "") -> tuple[bool, str]:
        """
        Send notification for a single outstanding quote.
        """
        payload = {
            "event": "quote_extracted",
            "timestamp": datetime.now().isoformat(),
            "quote": {
                "id": quote.id,
                "text": quote.text,
                "quality": quote.quality.value,
                "categories": [c.value for c in quote.categories],
                "timestamp": quote.timestamp,
                "talk_title": talk_title,
            },
        }

        return self.send(payload)

    def send_trend_alert(
        self,
        alert_type: str,
        message: str,
        data: dict[str, Any],
    ) -> tuple[bool, str]:
        """
        Send alert about trends (e.g., declining metrics).
        """
        payload = {
            "event": "trend_alert",
            "timestamp": datetime.now().isoformat(),
            "alert_type": alert_type,
            "message": message,
            "data": data,
        }

        return self.send(payload)


class SlackWebhook(WebhookSender):
    """
    Slack-specific webhook integration.
    """

    def send_analysis_complete(
        self,
        talk: Talk,
        metrics: DeliveryMetrics,
        quotes: QuoteCollection,
        aar_content: Optional[str] = None,
    ) -> tuple[bool, str]:
        """Send formatted Slack message for analysis completion."""

        # Build Slack blocks
        blocks = [
            {
                "type": "header",
                "text": {
                    "type": "plain_text",
                    "text": f"Talk Analysis Complete: {talk.metadata.title}",
                }
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Date:*\n{talk.metadata.date.strftime('%Y-%m-%d')}"},
                    {"type": "mrkdwn", "text": f"*Venue:*\n{talk.metadata.venue or 'N/A'}"},
                    {"type": "mrkdwn", "text": f"*Delivery Score:*\n{metrics.overall_delivery_score:.0f}/100"},
                    {"type": "mrkdwn", "text": f"*Filler Words:*\n{metrics.filler_analysis.total_count} ({metrics.filler_analysis.fillers_per_minute:.1f}/min)"},
                ]
            },
            {
                "type": "section",
                "fields": [
                    {"type": "mrkdwn", "text": f"*Quotes Found:*\n{len(quotes.quotes)} total"},
                    {"type": "mrkdwn", "text": f"*Outstanding:*\n{len(quotes.outstanding_quotes)}"},
                ]
            },
        ]

        # Add outstanding quotes
        for quote in quotes.outstanding_quotes[:3]:
            blocks.append({
                "type": "section",
                "text": {
                    "type": "mrkdwn",
                    "text": f">_{quote.text}_"
                }
            })

        payload = {"blocks": blocks}

        return self.send(payload)


class DiscordWebhook(WebhookSender):
    """
    Discord-specific webhook integration.
    """

    def send_analysis_complete(
        self,
        talk: Talk,
        metrics: DeliveryMetrics,
        quotes: QuoteCollection,
        aar_content: Optional[str] = None,
    ) -> tuple[bool, str]:
        """Send formatted Discord embed for analysis completion."""

        # Determine color based on score
        score = metrics.overall_delivery_score
        if score >= 80:
            color = 0x00FF00  # Green
        elif score >= 60:
            color = 0xFFFF00  # Yellow
        else:
            color = 0xFF0000  # Red

        embed = {
            "title": f"Talk Analysis: {talk.metadata.title}",
            "color": color,
            "fields": [
                {"name": "Date", "value": talk.metadata.date.strftime('%Y-%m-%d'), "inline": True},
                {"name": "Venue", "value": talk.metadata.venue or "N/A", "inline": True},
                {"name": "Delivery Score", "value": f"{score:.0f}/100", "inline": True},
                {"name": "Filler Words", "value": f"{metrics.filler_analysis.total_count}", "inline": True},
                {"name": "Quotes Found", "value": f"{len(quotes.quotes)}", "inline": True},
                {"name": "Outstanding", "value": f"{len(quotes.outstanding_quotes)}", "inline": True},
            ],
            "footer": {"text": "Talk Transcript Analyzer"},
            "timestamp": datetime.now().isoformat(),
        }

        # Add outstanding quotes as description
        if quotes.outstanding_quotes:
            quote_texts = [f"_{q.text[:150]}..._" if len(q.text) > 150 else f"_{q.text}_"
                         for q in quotes.outstanding_quotes[:2]]
            embed["description"] = "\n\n".join(quote_texts)

        payload = {"embeds": [embed]}

        return self.send(payload)


class ZapierWebhook(WebhookSender):
    """
    Zapier Webhook integration for connecting to 5000+ apps.
    """

    def send_to_zapier(
        self,
        event_type: str,
        data: dict[str, Any],
    ) -> tuple[bool, str]:
        """
        Send data to Zapier in a flat structure for easy mapping.
        """
        # Flatten nested data for Zapier
        flat_data = {
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
        }

        for key, value in data.items():
            if isinstance(value, dict):
                for sub_key, sub_value in value.items():
                    flat_data[f"{key}_{sub_key}"] = sub_value
            elif isinstance(value, list):
                flat_data[key] = json.dumps(value)
            else:
                flat_data[key] = value

        return self.send(flat_data)

    def send_analysis_complete(
        self,
        talk: Talk,
        metrics: DeliveryMetrics,
        quotes: QuoteCollection,
        aar_content: Optional[str] = None,
    ) -> tuple[bool, str]:
        """Send analysis data in Zapier-friendly format."""

        data = {
            "talk_id": talk.id,
            "talk_title": talk.metadata.title,
            "talk_date": talk.metadata.date.isoformat(),
            "talk_venue": talk.metadata.venue or "",
            "talk_topic": talk.metadata.topic or "",
            "talk_word_count": talk.word_count,
            "delivery_score": metrics.overall_delivery_score,
            "filler_count": metrics.filler_analysis.total_count,
            "fillers_per_minute": round(metrics.filler_analysis.fillers_per_minute, 2),
            "average_wpm": round(metrics.pacing_analysis.average_wpm, 1),
            "quotes_total": len(quotes.quotes),
            "quotes_outstanding": len(quotes.outstanding_quotes),
            "top_quote": quotes.outstanding_quotes[0].text if quotes.outstanding_quotes else "",
        }

        if aar_content:
            data["aar_summary"] = aar_content[:4000]  # Zapier has limits

        return self.send_to_zapier("analysis_complete", data)
