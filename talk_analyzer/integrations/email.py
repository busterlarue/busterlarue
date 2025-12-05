"""
Email integration for sending AAR artifacts and quotes.

Supports both SMTP and SendGrid.
"""

import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.application import MIMEApplication
from typing import Optional
from pathlib import Path
import json

from ..config import default_config, AnalyzerConfig
from ..models.talk import Talk
from ..models.quotes import QuoteCollection


class EmailSender:
    """
    Send emails with AAR artifacts and quotes.
    """

    def __init__(self, config: Optional[AnalyzerConfig] = None):
        self.config = config or default_config
        self._validate_config()

    def _validate_config(self) -> bool:
        """Check if email configuration is available."""
        if self.config.sendgrid_api_key:
            return True
        if self.config.smtp_host and self.config.smtp_user:
            return True
        return False

    def is_configured(self) -> bool:
        """Check if email sending is properly configured."""
        return self._validate_config()

    def send_aar(
        self,
        to_email: str,
        talk: Talk,
        aar_content: str,
        attach_quotes: bool = True,
        quotes: Optional[QuoteCollection] = None,
    ) -> bool:
        """
        Send an After Action Review via email.

        Args:
            to_email: Recipient email address
            talk: The Talk object
            aar_content: Markdown AAR content
            attach_quotes: Include quotes as attachment
            quotes: QuoteCollection to attach

        Returns:
            True if sent successfully
        """
        if not self.is_configured():
            raise ValueError("Email not configured. Set SMTP or SendGrid credentials.")

        subject = f"After Action Review: {talk.metadata.title}"

        # Build HTML email body
        html_body = self._markdown_to_html(aar_content)

        # Prepare attachments
        attachments = []
        if attach_quotes and quotes:
            quotes_json = json.dumps(quotes.to_dict(), indent=2)
            attachments.append(("quotes.json", quotes_json.encode()))

        # Send via appropriate method
        if self.config.sendgrid_api_key:
            return self._send_via_sendgrid(to_email, subject, html_body, attachments)
        else:
            return self._send_via_smtp(to_email, subject, html_body, attachments)

    def send_quotes_digest(
        self,
        to_email: str,
        quotes: QuoteCollection,
        subject: str = "Your Quote Digest",
    ) -> bool:
        """
        Send a digest of quotes via email.
        """
        if not self.is_configured():
            raise ValueError("Email not configured.")

        # Build email body
        lines = ["<h1>Quote Digest</h1>"]
        lines.append(f"<p><em>{len(quotes.quotes)} quotes for your review</em></p>")

        # Outstanding quotes
        outstanding = quotes.outstanding_quotes
        if outstanding:
            lines.append("<h2>Outstanding Quotes</h2>")
            for quote in outstanding:
                lines.append(f"<blockquote>{quote.text}</blockquote>")
                if quote.categories:
                    tags = ", ".join(c.value for c in quote.categories)
                    lines.append(f"<p><small>Tags: {tags}</small></p>")

        # All other quotes
        others = [q for q in quotes.quotes if q not in outstanding]
        if others:
            lines.append("<h2>More Quotes</h2>")
            for quote in others[:20]:
                lines.append(f"<blockquote>{quote.text}</blockquote>")

        html_body = "\n".join(lines)

        if self.config.sendgrid_api_key:
            return self._send_via_sendgrid(to_email, subject, html_body, [])
        else:
            return self._send_via_smtp(to_email, subject, html_body, [])

    def _send_via_smtp(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        attachments: list[tuple[str, bytes]],
    ) -> bool:
        """Send email via SMTP."""
        msg = MIMEMultipart()
        msg["From"] = self.config.email_from or self.config.smtp_user
        msg["To"] = to_email
        msg["Subject"] = subject

        # Add HTML body
        msg.attach(MIMEText(html_body, "html"))

        # Add attachments
        for filename, content in attachments:
            part = MIMEApplication(content, Name=filename)
            part["Content-Disposition"] = f'attachment; filename="{filename}"'
            msg.attach(part)

        try:
            with smtplib.SMTP(self.config.smtp_host, self.config.smtp_port) as server:
                server.starttls()
                server.login(self.config.smtp_user, self.config.smtp_password)
                server.send_message(msg)
            return True
        except Exception as e:
            print(f"Failed to send email: {e}")
            return False

    def _send_via_sendgrid(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        attachments: list[tuple[str, bytes]],
    ) -> bool:
        """
        Send email via SendGrid API.

        Note: Requires sendgrid package: pip install sendgrid
        """
        try:
            from sendgrid import SendGridAPIClient
            from sendgrid.helpers.mail import (
                Mail, Attachment, FileContent, FileName,
                FileType, Disposition
            )
            import base64
        except ImportError:
            print("SendGrid not installed. Run: pip install sendgrid")
            return False

        message = Mail(
            from_email=self.config.email_from or "noreply@example.com",
            to_emails=to_email,
            subject=subject,
            html_content=html_body,
        )

        # Add attachments
        for filename, content in attachments:
            encoded = base64.b64encode(content).decode()
            attachment = Attachment(
                FileContent(encoded),
                FileName(filename),
                FileType("application/json"),
                Disposition("attachment"),
            )
            message.add_attachment(attachment)

        try:
            sg = SendGridAPIClient(self.config.sendgrid_api_key)
            response = sg.send(message)
            return response.status_code in (200, 201, 202)
        except Exception as e:
            print(f"Failed to send via SendGrid: {e}")
            return False

    def _markdown_to_html(self, markdown: str) -> str:
        """
        Convert markdown to HTML.

        Note: For full markdown support, install markdown package.
        This provides basic conversion.
        """
        try:
            import markdown
            return markdown.markdown(markdown, extensions=['tables', 'fenced_code'])
        except ImportError:
            # Basic conversion without markdown package
            html = markdown
            # Headers
            import re
            html = re.sub(r'^### (.+)$', r'<h3>\1</h3>', html, flags=re.MULTILINE)
            html = re.sub(r'^## (.+)$', r'<h2>\1</h2>', html, flags=re.MULTILINE)
            html = re.sub(r'^# (.+)$', r'<h1>\1</h1>', html, flags=re.MULTILINE)
            # Bold
            html = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', html)
            # Italic
            html = re.sub(r'\*(.+?)\*', r'<em>\1</em>', html)
            # Lists
            html = re.sub(r'^- (.+)$', r'<li>\1</li>', html, flags=re.MULTILINE)
            # Blockquotes
            html = re.sub(r'^> (.+)$', r'<blockquote>\1</blockquote>', html, flags=re.MULTILINE)
            # Line breaks
            html = html.replace('\n\n', '</p><p>')
            html = f"<p>{html}</p>"
            return html
