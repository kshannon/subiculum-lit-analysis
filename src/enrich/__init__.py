"""
Citation enrichment module.

Provides citation data from external APIs for papers missing references in PubMed.
"""

from .crossref_client import CrossRefClient
from .semantic_scholar_client import SemanticScholarClient
from .citation_enricher import CitationEnricher

__all__ = [
    'CrossRefClient',
    'SemanticScholarClient',
    'CitationEnricher'
]
