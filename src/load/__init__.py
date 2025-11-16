"""
Load module - Database insertion and transaction management

Components for loading structured data into SQLite database:
- DatabaseWriter: Transactional insertion of papers and relationships

Author: Kyle Shannon
Date: 2025-11-11
"""

from .db_writer import DatabaseWriter

__all__ = ["DatabaseWriter"]
