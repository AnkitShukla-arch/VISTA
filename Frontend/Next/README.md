# VISTA Dashboard

The Next.js dashboard lives in this directory. Its start screen lets people choose a Technician or Doctor workspace. Technicians get the ingestion pipeline, OCR/ETL, clinical fingerprinting, embedding, semantic box assignment, storage, analytics, and document tools. Doctors get a focused report search, natural-language patient/condition queries, report previews, and a report collection.

Key routes: `/` role chooser, `/technician` ingestion and pipeline, `/doctor` clinical workspace, `/doctor/reports` doctor report collection, `/search`, `/boxes`, `/analytics`, and `/documents` for technician tools.

## Run the dashboard

```powershell
cd Frontend/Next
npm.cmd install
npm.cmd run dev
```

Open [http://localhost:3000](http://localhost:3000). The local `.env.local` points the frontend at the FastAPI server on port 8000.

## Connect the VISTA API

From the repository root, start the FastAPI wrapper:

```powershell
..\.venv\Scripts\python.exe -m uvicorn Backend.api:app --reload --port 8000
```

Create `Frontend/Next/.env.local` with:

```env
NEXT_PUBLIC_API_URL=http://127.0.0.1:8000
```

Restart Next.js after changing the environment variable. The API enables CORS for local dashboard development; for deployment, set `allow_origins` in `Backend/api.py` to the dashboard's deployed origin.

## Data and routes

Existing analytics and visualizations fall back to `mocks/data.ts` when the API is unavailable; uploading requires the API. The API exposes `/ingestion/jobs` and `/ingestion/jobs/{id}` for live processing, `/query` for parameterized DuckDB count queries, plus `/search`, `/boxes`, `/boxes/{id}/documents`, `/documents`, `/documents/{id}`, `/projection`, and `/metrics`.

Supported upload formats are PDF, DOCX, CSV/TSV, JSON/JSONL, XLSX, TXT/Markdown, XML/HTML, and common image formats. Digital PDFs use their text layer; scanned PDFs and images use PaddleOCR. Each uploaded vector is matched to the existing box-summary vectors and saved with its clinical metadata. Raw files are retained in MinIO when available, with a local raw-layer copy as fallback.
