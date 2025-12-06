"""
Shared utilities for the subiculum literature analysis pipeline.

This package provides common infrastructure used across all pipeline components:
- logger: Unified logging for entire workflow
- database: Standardized database access for scripts and notebooks
- credentials: Secure credential management for API access
"""

from .logger import get_logger
from .database import get_connection, init_test_db, cleanup_test_db
from .credentials import get_api_credentials, get_all_enrichment_credentials

__all__ = [
    'get_logger',
    'get_connection',
    'init_test_db',
    'cleanup_test_db',
    'get_api_credentials',
    'get_all_enrichment_credentials'
]
