"""Compatibility shim for legacy imports.

The canonical database implementation lives in the database package.
"""
from database.database import Database, IntegrityError, init_database

__all__ = ["Database", "IntegrityError", "init_database"]
