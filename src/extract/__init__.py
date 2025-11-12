"""
Extract module - PubMed API interaction

Components for extracting data from PubMed E-utilities API:
- PubMedAPIClient: ESearch and EFetch operations with inline rate limiting
"""

from .api_client import PubMedAPIClient, SearchResult

__all__ = [
    "PubMedAPIClient",
    "SearchResult",
]
