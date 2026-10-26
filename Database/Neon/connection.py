"""Neon / PostgreSQL persistence for uploaded reports and ingestion jobs."""
import json
from typing import Optional, Any, Dict, List


class NeonWarehouseManager:
    """Manages connection and relational queries for the Neon PostgreSQL warehouse."""

    def __init__(self, connection_url: str):
        self.connection_url = connection_url
        self._engine = None
        self._schema_ready = False

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

    def ensure_schema(self) -> None:
        if self._schema_ready:
            return
        from sqlalchemy import text

        with self.engine.begin() as conn:
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS vista_uploaded_reports (
                    doc_id TEXT PRIMARY KEY,
                    job_id TEXT NOT NULL,
                    record JSONB NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """))
            conn.execute(text("""
                CREATE TABLE IF NOT EXISTS vista_ingestion_jobs (
                    job_id TEXT PRIMARY KEY,
                    payload JSONB NOT NULL,
                    updated_at TIMESTAMPTZ NOT NULL DEFAULT now()
                )
            """))
        self._schema_ready = True

    def upsert_reports(self, records: List[Dict[str, Any]]) -> None:
        if not records:
            return
        from sqlalchemy import text

        self.ensure_schema()
        statement = text("""
            INSERT INTO vista_uploaded_reports (doc_id, job_id, record, updated_at)
            VALUES (:doc_id, :job_id, CAST(:record AS JSONB), now())
            ON CONFLICT (doc_id) DO UPDATE SET
                job_id = EXCLUDED.job_id,
                record = EXCLUDED.record,
                updated_at = now()
        """)
        values = [
            {
                "doc_id": str(record["doc_id"]),
                "job_id": str(record.get("job_id") or "unknown"),
                "record": json.dumps(record, ensure_ascii=False),
            }
            for record in records
        ]
        with self.engine.begin() as conn:
            conn.execute(statement, values)

    def load_reports(self) -> List[Dict[str, Any]]:
        from sqlalchemy import text

        self.ensure_schema()
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT record FROM vista_uploaded_reports ORDER BY updated_at DESC"
            )).scalars().all()
        return [json.loads(row) if isinstance(row, str) else dict(row) for row in rows]

    def upsert_job(self, job: Dict[str, Any]) -> None:
        from sqlalchemy import text

        self.ensure_schema()
        statement = text("""
            INSERT INTO vista_ingestion_jobs (job_id, payload, updated_at)
            VALUES (:job_id, CAST(:payload AS JSONB), now())
            ON CONFLICT (job_id) DO UPDATE SET
                payload = EXCLUDED.payload,
                updated_at = now()
        """)
        with self.engine.begin() as conn:
            conn.execute(statement, {
                "job_id": str(job["job_id"]),
                "payload": json.dumps(job, ensure_ascii=False),
            })

    def get_job(self, job_id: str) -> Optional[Dict[str, Any]]:
        from sqlalchemy import text

        self.ensure_schema()
        with self.engine.connect() as conn:
            row = conn.execute(text(
                "SELECT payload FROM vista_ingestion_jobs WHERE job_id = :job_id"
            ), {"job_id": job_id}).scalar_one_or_none()
        if row is None:
            return None
        return json.loads(row) if isinstance(row, str) else dict(row)

    def load_jobs(self, limit: int = 20) -> List[Dict[str, Any]]:
        from sqlalchemy import text

        self.ensure_schema()
        with self.engine.connect() as conn:
            rows = conn.execute(text(
                "SELECT payload FROM vista_ingestion_jobs ORDER BY updated_at DESC LIMIT :limit"
            ), {"limit": limit}).scalars().all()
        return [json.loads(row) if isinstance(row, str) else dict(row) for row in rows]
