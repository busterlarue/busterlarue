"""
Talk Transcript Analyzer

A comprehensive tool for analyzing talk transcripts, extracting insights,
tracking delivery metrics, and generating after-action review artifacts.
"""

__version__ = "0.1.0"
__author__ = "Buster Larue"

from .models.talk import Talk, TalkMetadata, Segment
from .models.delivery import DeliveryMetrics, FillerAnalysis, PacingAnalysis
from .models.quotes import Quote, QuoteCollection
from .artifacts.aar import AfterActionReview

__all__ = [
    "Talk",
    "TalkMetadata",
    "Segment",
    "DeliveryMetrics",
    "FillerAnalysis",
    "PacingAnalysis",
    "Quote",
    "QuoteCollection",
    "AfterActionReview",
]
