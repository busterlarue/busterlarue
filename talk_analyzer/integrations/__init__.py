"""External integrations for the Talk Transcript Analyzer."""

from .email import EmailSender
from .notion import NotionClient
from .webhooks import WebhookSender

__all__ = ["EmailSender", "NotionClient", "WebhookSender"]
