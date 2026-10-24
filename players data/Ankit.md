# Ankit — object storage and warehouse layer

## Contribution

Ankit owns the storage/warehouse responsibility: retain original report files in object storage and provide a relational interface for structured metadata. The design keeps source file bytes separate from searchable metadata and links report records through a stable document identifier.

## Workflow

1. Configure a MinIO client and ensure the target bucket exists.
2. Store the original report as an object and retain its object path for retrieval.
3. Use the Neon/PostgreSQL adapter for relational metadata queries when configured.
4. Keep document identifiers and metadata consistent across storage and API layers.

## Technologies

MinIO, S3-compatible object storage, Neon PostgreSQL, SQLAlchemy, SQL, and Python.

## Source code

- `Database/MinIO/client.py` — MinIO storage manager and file upload/download methods.
- `Database/Neon/connection.py` — lazy SQLAlchemy connection wrapper and query execution.
- `Backend/ingestion.py` — current upload source-file persistence and metadata persistence flow.
- `project/code/vista_pipeline/__init__.py` — helpers to store Parquet, JSON, and text in MinIO.

## Representative code excerpts

The MinIO wrapper uploads a local file and returns the chosen object name:

```python
def upload_file(self, file_path: Path, object_name: Optional[str] = None) -> str:
    file_path = Path(file_path)
    obj_name = object_name or file_path.name
    self.client.fput_object(self.bucket_name, obj_name, str(file_path))
    return obj_name
```

The Neon adapter creates a SQLAlchemy engine lazily and uses bound parameters for query execution:

```python
@property
def engine(self):
    if self._engine is None:
        from sqlalchemy import create_engine
        self._engine = create_engine(self.connection_url, pool_pre_ping=True)
    return self._engine

def execute_query(self, query, params=None):
    from sqlalchemy import text
    with self.engine.connect() as conn:
        result = conn.execute(text(query), params or {})
        if result.returns_rows:
            return [dict(row._mapping) for row in result]
        return []
```

## Implementation note

## Detailed implementation walkthrough

### Object storage responsibilities

- MinIO stores file bytes as objects in named buckets.
- The wrapper class is `MinIOStorageManager` in `Database/MinIO/client.py`.
- Client construction is lazy, so importing the module does not immediately connect.
- The client checks whether the target bucket exists before using it.
- A missing bucket is created by the wrapper.
- `upload_file()` accepts a local path and an optional object name.
- Without an explicit object name, the local file name is used.
- The method delegates file transfer to MinIO’s `fput_object()` method.
- The method returns the object name so the caller can retain a reference.
- `download_file()` ensures the destination parent directory exists.
- It then asks MinIO to copy the object to the selected local target path.
- Object storage separates large raw files from relational metadata.
- The source file can be downloaded only when a user or downstream job needs its bytes.
- Object keys should remain stable and preserve report provenance.
- Production credentials and endpoint values should come from secure configuration.
- Credentials must not be committed into source control or documentation examples.

### Phase 1 MinIO layout

- The Phase 1 ETL shared helper uses the `vista-lake` bucket by default.
- The `raw/` prefix stores source files unchanged.
- The `clean/` prefix stores cleaned Parquet outputs and the cleaning manifest.
- The `summaries/` prefix stores JSON profiles and a Markdown roll-up.
- The `reports/` prefix can hold a phase-run report.
- Prefixes act as logical folders in the S3-compatible object namespace.
- MinIO object versioning is enabled when the shared helper creates a bucket.
- The upload code uses explicit content types for Parquet, JSON, and text artifacts.
- Aashita’s ETL uses these shared helpers for the raw, clean, and summary layers.
- Ankit’s assignment covers the object-storage and warehouse design/integration.
- This means MinIO is a shared platform component across the Phase 1 and upload flows.

### Neon/PostgreSQL adapter

- `NeonWarehouseManager` in `Database/Neon/connection.py` wraps a SQLAlchemy engine.
- It accepts a connection URL supplied by configuration or the caller.
- The engine is created lazily on first access.
- `pool_pre_ping=True` asks SQLAlchemy to check a pooled connection before reuse.
- `execute_query()` wraps SQL text with SQLAlchemy’s `text()` helper.
- Query values can be supplied separately through a parameter dictionary.
- Result rows are converted to plain dictionaries for callers.
- Statements that do not return rows produce an empty result list.
- The adapter does not hardcode the database URL in the module.
- The repository does not expose a complete deployed Neon schema in this wrapper.
- The class is an adapter boundary for relational queries, not the full warehouse data model.
- A real deployment must supply a valid connection URL and schema/migrations.
- The current upload pipeline described below does not call this adapter directly.

### Current upload persistence path

- `Backend/ingestion.py` handles user-uploaded report files.
- It saves an unchanged local copy under the upload/raw storage area.
- When configured for a non-local MinIO endpoint, it attempts to upload the source object.
- The object key is tied to the upload/job identifier and sanitized file name.
- The returned storage reference is kept as part of the job result.
- If object storage is unavailable, the current flow can retain the local raw file reference.
- The report is separately parsed, fingerprinted, and embedded by pipeline stages.
- The current metadata persistence path creates an `uploaded_reports` DuckDB table.
- That table stores document ID, job ID, source filename, title, specialty, patient, age, conditions, box ID, summary, raw text, vector JSON, and ingestion time.
- The vector is serialized as JSON in that table rather than a dedicated vector column.
- The code reads back a report count to verify that the warehouse insert is queryable.
- This path currently uses DuckDB and should not be described as a live Neon write.
- Neon adapter code exists separately for a future or separately configured PostgreSQL path.

### Document identity and metadata linkage

- Every report needs a stable document identifier for API operations.
- Uploaded files receive IDs derived from their job ID and record sequence.
- Phase 2 dataset entries receive deterministic hash-based IDs.
- The source filename is retained as provenance.
- Patient and specialty fields support user-facing filters and report labels.
- The box ID links a record to a semantic group.
- The raw text is retained for previews and later text matching.
- The embedding is retained for similarity and semantic retrieval.
- Storage object names should be stored with the record if reports must be downloadable.
- Search metadata should not be confused with the raw object itself.
- The identifier serves as the join key between report records and their stored source file.
- Changes to ID generation need a migration or a compatibility strategy for existing records.

## Data lifecycle and responsibilities

- A user or batch job supplies a source report.
- Raw-file persistence stores original bytes without changing report content.
- OCR or native parsing produces machine-readable text.
- Fingerprinting extracts structured clinical fields.
- Embedding and box assignment enrich the report with semantic references.
- The warehouse layer stores metadata needed to find, filter, and count records.
- The UI calls the API and does not directly connect to MinIO, Neon, or DuckDB.
- A report preview reads extracted text and associated metadata from the API.
- A download feature would use the source object key to retrieve original bytes.
- This separation permits the semantic index to remain small while raw reports stay in object storage.
- Storage access should be controlled independently from vector search access.
- Raw medical files and extracted PHI require appropriate protection in a real deployment.

## Technology and usage details

- **MinIO:** Stores raw report files and Phase 1 data layers behind an S3-compatible API.
- **Neon:** Managed PostgreSQL target represented by the SQLAlchemy adapter.
- **SQLAlchemy:** Connection pooling and parameterized SQL execution for PostgreSQL.
- **DuckDB:** Current local metadata persistence/query store used by the upload runtime.
- **JSON:** Serializes clinical conditions and vectors in current local persistence.
- **FastAPI:** Provides the application API boundary between frontend and storage logic.
- The MinIO endpoint is configurable for local or remote deployments.
- The Neon connection URL is passed into the adapter rather than embedded in code.
- The current object manager supports upload and download of local files.
- The shared Phase 1 helpers additionally support Parquet, JSON, and text upload.
- The current Neon class exposes query execution, not explicit ORM models or migrations.
- An operational deployment needs documented bucket lifecycle and database backup policies.

## Design decisions and rationale

- Object storage is appropriate for large binary reports and immutable source evidence.
- A relational database is appropriate for structured metadata filters and joins.
- Stable IDs keep object references and metadata records linkable.
- Lazy connections avoid startup cost for routes that do not use the backend.
- Parameter binding keeps values out of SQL syntax construction.
- Separate raw and processed objects keep provenance available after transformation.
- Storage adapters reduce application coupling to one provider’s client calls.
- A local DuckDB path supports development without requiring a hosted PostgreSQL connection.
- Production configuration should switch the metadata path through an explicit adapter, not hidden assumptions.
- A failed raw upload should be distinguishable from a successful metadata write.
- Warehouse insertion should be transactional when raw object and metadata consistency is required.
- Object keys should not rely solely on potentially repeated user-provided file names.
- Local fallback files need retention and access-control rules if used outside development.

## Implementation status and caveats

- The repository has MinIO client code and Phase 1 MinIO upload helpers.
- The repository has a Neon/PostgreSQL connection wrapper.
- The project documentation assigns MinIO and Neon warehouse work to Ankit.
- The current per-upload path writes `uploaded_reports` records to DuckDB.
- The code observed in this repository does not call `NeonWarehouseManager` from that per-upload persistence path.
- Therefore, do not claim that every uploaded report is currently persisted to Neon based on the adapter alone.
- Confirm deployment configuration before describing a remote database connection as active.
- The MinIO wrapper itself contains development-friendly defaults; deployed secrets should be supplied securely.
- The per-upload DuckDB table is metadata persistence, not a substitute for an operationally managed production warehouse.
- The Frontend uses the API and does not directly invoke these database clients.

## Suggested demonstration points

- Show the raw object key for an uploaded report.
- Show how the MinIO wrapper returns an object name for later reference.
- Explain bucket and prefix naming for raw, clean, and summaries layers.
- Show the source filename and stable document ID on a metadata row.
- Explain how Neon connection configuration is injected.
- Demonstrate parameter binding through the SQLAlchemy adapter.
- Show the current DuckDB upload table and its stored metadata fields.
- Explain why source files and searchable metadata are stored separately.
- Distinguish the implemented local DuckDB persistence from the Neon adapter.
- Explain what must be configured before the Neon path can be called live.

## Contribution summary for a project report

Ankit owns VISTA’s object-storage and warehouse layer. The project includes a MinIO wrapper for uploading and downloading original medical reports, shared helpers for storing processed Parquet and summary artifacts, and a SQLAlchemy-based adapter for Neon PostgreSQL queries. Report IDs and source metadata link clinical records to their source files. In the current upload runtime, the metadata insert is implemented in DuckDB, while the Neon adapter is present as a separate integration boundary; this distinction should be stated when reporting the implementation status.

## Terms used in this contribution

- **Object storage:** Key-addressed storage for files and large binary objects.
- **Bucket:** Top-level container for object keys in MinIO/S3.
- **Object key:** Path-like identifier for an object inside a bucket.
- **Warehouse:** Structured store for report metadata and analytical queries.
- **Neon:** Managed PostgreSQL service targeted by the adapter.
- **SQLAlchemy:** Python library used to manage SQL connections and statements.
- **Connection URL:** Configuration string identifying the target database.
- **Stable document ID:** Identifier used to connect report metadata and source references.
- **Provenance:** Source path and processing information associated with a record.
- **Adapter:** Wrapper that isolates application code from a storage/database API.
- **Fallback storage:** Local file copy used when remote storage is unavailable.
- **Transaction:** Group of database operations committed or rolled back together.
- **PHI:** Protected health information contained in medical records.

The repository contains MinIO and Neon connection/storage adapters. In the current upload pipeline, `Backend/ingestion.py` persists searchable upload metadata in local DuckDB; that upload path does not call `NeonWarehouseManager`. Describe Neon as the project’s warehouse adapter/design unless the deployed environment has separately wired it in. MinIO is shared by the Phase 1 ETL and report-storage flows.
