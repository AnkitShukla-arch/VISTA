"""
Neon / PostgreSQL Data Warehouse Connection and Schema.
Owner: Ankit Shukla (Storage & Data Warehouse Engineer)
"""
from typing import Optional, Any, Dict, List


class NeonWarehouseManager:
    """Manages connection and relational queries for the Neon PostgreSQL warehouse."""

    def __init__(self, connection_url: str):
        self.connection_url = connection_url
        self._engine = None

    @property
    def engine(self):
        """Lazy loader for SQLAlchemy engine."""
        if self._engine is None:
            try:
                from sqlalchemy import create_engine

                self._engine = create_engine(self.connection_url, pool_pre_ping=True)
            except ImportError:
                raise ImportError(
                    "sqlalchemy is required. Install via: pip install sqlalchemy psycopg2-binary"
                )
        return self._engine

    def execute_query(self, query: str, params: Optional[Dict[str, Any]] = None) -> List[Dict[str, Any]]:
        """Execute a SQL query and return results as dictionaries."""
        from sqlalchemy import text

        with self.engine.connect() as conn:
            result = conn.execute(text(query), params or {})
            if result.returns_rows:
                return [dict(row._mapping) for row in result]
            return []
