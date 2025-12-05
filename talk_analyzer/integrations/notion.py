"""
Notion integration for syncing quotes and talk summaries.

Requires: pip install notion-client
"""

from typing import Optional
from datetime import datetime

from ..config import default_config, AnalyzerConfig
from ..models.talk import Talk
from ..models.quotes import Quote, QuoteCollection
from ..models.delivery import DeliveryMetrics


class NotionClient:
    """
    Sync talks, quotes, and insights to Notion.
    """

    def __init__(self, config: Optional[AnalyzerConfig] = None):
        self.config = config or default_config
        self._client = None

    def is_configured(self) -> bool:
        """Check if Notion is properly configured."""
        return bool(self.config.notion_api_key and self.config.notion_database_id)

    def _get_client(self):
        """Get or create Notion client."""
        if self._client is None:
            if not self.is_configured():
                raise ValueError(
                    "Notion not configured. Set NOTION_API_KEY and NOTION_DATABASE_ID."
                )
            try:
                from notion_client import Client
                self._client = Client(auth=self.config.notion_api_key)
            except ImportError:
                raise ImportError("notion-client not installed. Run: pip install notion-client")
        return self._client

    def sync_quote(self, quote: Quote, talk_title: str = "") -> Optional[str]:
        """
        Sync a single quote to Notion.

        Returns the Notion page ID if successful.
        """
        client = self._get_client()

        properties = {
            "Quote": {
                "title": [{"text": {"content": quote.text[:100]}}]
            },
            "Full Text": {
                "rich_text": [{"text": {"content": quote.text}}]
            },
            "Quality": {
                "select": {"name": quote.quality.value.title()}
            },
            "Talk": {
                "rich_text": [{"text": {"content": talk_title}}]
            },
            "Categories": {
                "multi_select": [{"name": c.value} for c in quote.categories]
            },
            "Created": {
                "date": {"start": quote.created_at.isoformat()}
            },
            "Reuse Count": {
                "number": quote.reuse_count
            },
            "Favorite": {
                "checkbox": quote.is_favorite
            },
        }

        if quote.tags:
            properties["Tags"] = {
                "multi_select": [{"name": tag} for tag in quote.tags[:10]]
            }

        try:
            response = client.pages.create(
                parent={"database_id": self.config.notion_database_id},
                properties=properties,
            )
            return response["id"]
        except Exception as e:
            print(f"Failed to sync quote to Notion: {e}")
            return None

    def sync_quotes(self, quotes: QuoteCollection, talk_title: str = "") -> list[str]:
        """
        Sync multiple quotes to Notion.

        Returns list of created Notion page IDs.
        """
        page_ids = []
        for quote in quotes.quotes:
            page_id = self.sync_quote(quote, talk_title)
            if page_id:
                page_ids.append(page_id)
        return page_ids

    def sync_talk_summary(
        self,
        talk: Talk,
        metrics: Optional[DeliveryMetrics] = None,
        aar_content: str = "",
    ) -> Optional[str]:
        """
        Sync a talk summary to Notion.

        Returns the Notion page ID if successful.
        """
        client = self._get_client()

        properties = {
            "Title": {
                "title": [{"text": {"content": talk.metadata.title}}]
            },
            "Date": {
                "date": {"start": talk.metadata.date.isoformat()[:10]}
            },
            "Venue": {
                "rich_text": [{"text": {"content": talk.metadata.venue or ""}}]
            },
            "Topic": {
                "rich_text": [{"text": {"content": talk.metadata.topic or ""}}]
            },
            "Audience": {
                "select": {"name": talk.metadata.audience_type.value.replace("_", " ").title()}
            },
            "Duration": {
                "rich_text": [{"text": {"content": talk.metadata.duration_formatted}}]
            },
            "Word Count": {
                "number": talk.word_count
            },
        }

        if metrics:
            properties["Delivery Score"] = {"number": metrics.overall_delivery_score}
            properties["Filler Count"] = {"number": metrics.filler_analysis.total_count}
            properties["Avg WPM"] = {"number": round(metrics.pacing_analysis.average_wpm)}

        if talk.metadata.tags:
            properties["Tags"] = {
                "multi_select": [{"name": tag} for tag in talk.metadata.tags[:10]]
            }

        # Create page with AAR content as body
        children = []
        if aar_content:
            # Split into chunks (Notion has block size limits)
            for line in aar_content.split("\n"):
                if line.startswith("# "):
                    children.append({
                        "object": "block",
                        "type": "heading_1",
                        "heading_1": {
                            "rich_text": [{"text": {"content": line[2:]}}]
                        }
                    })
                elif line.startswith("## "):
                    children.append({
                        "object": "block",
                        "type": "heading_2",
                        "heading_2": {
                            "rich_text": [{"text": {"content": line[3:]}}]
                        }
                    })
                elif line.startswith("### "):
                    children.append({
                        "object": "block",
                        "type": "heading_3",
                        "heading_3": {
                            "rich_text": [{"text": {"content": line[4:]}}]
                        }
                    })
                elif line.startswith("> "):
                    children.append({
                        "object": "block",
                        "type": "quote",
                        "quote": {
                            "rich_text": [{"text": {"content": line[2:]}}]
                        }
                    })
                elif line.startswith("- "):
                    children.append({
                        "object": "block",
                        "type": "bulleted_list_item",
                        "bulleted_list_item": {
                            "rich_text": [{"text": {"content": line[2:]}}]
                        }
                    })
                elif line.strip():
                    children.append({
                        "object": "block",
                        "type": "paragraph",
                        "paragraph": {
                            "rich_text": [{"text": {"content": line}}]
                        }
                    })

        try:
            response = client.pages.create(
                parent={"database_id": self.config.notion_database_id},
                properties=properties,
                children=children[:100],  # Notion limit
            )
            return response["id"]
        except Exception as e:
            print(f"Failed to sync talk to Notion: {e}")
            return None

    def create_quotes_database(self, parent_page_id: str) -> Optional[str]:
        """
        Create a new Notion database for quotes.

        Returns the database ID if successful.
        """
        client = self._get_client()

        try:
            response = client.databases.create(
                parent={"page_id": parent_page_id},
                title=[{"text": {"content": "Talk Quotes"}}],
                properties={
                    "Quote": {"title": {}},
                    "Full Text": {"rich_text": {}},
                    "Quality": {
                        "select": {
                            "options": [
                                {"name": "Outstanding", "color": "green"},
                                {"name": "Excellent", "color": "blue"},
                                {"name": "Good", "color": "yellow"},
                                {"name": "Fair", "color": "gray"},
                            ]
                        }
                    },
                    "Talk": {"rich_text": {}},
                    "Categories": {
                        "multi_select": {
                            "options": [
                                {"name": "inspiring", "color": "purple"},
                                {"name": "insightful", "color": "blue"},
                                {"name": "practical", "color": "green"},
                                {"name": "memorable", "color": "yellow"},
                                {"name": "call_to_action", "color": "red"},
                            ]
                        }
                    },
                    "Tags": {"multi_select": {}},
                    "Created": {"date": {}},
                    "Reuse Count": {"number": {}},
                    "Favorite": {"checkbox": {}},
                },
            )
            return response["id"]
        except Exception as e:
            print(f"Failed to create Notion database: {e}")
            return None

    def query_quotes(
        self,
        quality: Optional[str] = None,
        category: Optional[str] = None,
        favorite_only: bool = False,
    ) -> list[dict]:
        """
        Query quotes from Notion database.
        """
        client = self._get_client()

        filters = []
        if quality:
            filters.append({
                "property": "Quality",
                "select": {"equals": quality.title()}
            })
        if category:
            filters.append({
                "property": "Categories",
                "multi_select": {"contains": category}
            })
        if favorite_only:
            filters.append({
                "property": "Favorite",
                "checkbox": {"equals": True}
            })

        query_filter = None
        if filters:
            if len(filters) == 1:
                query_filter = filters[0]
            else:
                query_filter = {"and": filters}

        try:
            if query_filter:
                response = client.databases.query(
                    database_id=self.config.notion_database_id,
                    filter=query_filter,
                )
            else:
                response = client.databases.query(
                    database_id=self.config.notion_database_id,
                )
            return response.get("results", [])
        except Exception as e:
            print(f"Failed to query Notion: {e}")
            return []
