#!/usr/bin/env python3
"""
Citation Enrichment Script

Enriches citation data by fetching reference lists from external APIs
(CrossRef and Semantic Scholar) for papers missing citation data in PubMed.

Usage:
    python scripts/enrich_citations.py [--limit N] [--test] [--require-api-keys]

Arguments:
    --limit N           Process only N papers (for testing)
    --test              Use test.db instead of production database
    --require-api-keys  Fail if API keys not provided (default: optional)
"""

import sys
import argparse
from pathlib import Path

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from src.utils.credentials import get_all_enrichment_credentials
from src.enrich.citation_enricher import CitationEnricher


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description='Enrich citation data from external APIs'
    )
    parser.add_argument(
        '--limit',
        type=int,
        help='Limit number of papers to process (for testing)'
    )
    parser.add_argument(
        '--test',
        action='store_true',
        help='Use test.db instead of production database'
    )
    parser.add_argument(
        '--require-api-keys',
        action='store_true',
        help='Require API keys (fail if not provided)'
    )
    args = parser.parse_args()

    # Get credentials
    credentials = get_all_enrichment_credentials(
        require_api_keys=args.require_api_keys
    )

    # Initialize enricher
    enricher = CitationEnricher(
        crossref_email=credentials['crossref']['email'],
        semantic_scholar_api_key=credentials['semantic_scholar']['api_key'],
        test_mode=args.test
    )

    # Run enrichment
    enricher.run(limit=args.limit)


if __name__ == "__main__":
    main()
