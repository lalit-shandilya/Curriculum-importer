# Curriculum Importer API Endpoints

This document explains all API endpoints in one place, including request format, response format, and practical usage flow.

## Base URL

- Local: `http://127.0.0.1:8000`
- Swagger UI: `http://127.0.0.1:8000/docs`

## Quick Start Flow

1. Start server:
   - `python main.py --api`
2. Run one-field ingestion:
   - `POST /ingest-ncert-simple`
3. Track background status:
   - `GET /results/{job_id}`
4. Query RAG index:
   - `POST /rag/query`

---

## 1) Discover NCERT PDF URLs

### `GET /discover-ncert`

Discover PDF links from the NCERT syllabus page.

### Query Params

- `syllabus_url` (optional)
  - default: `https://ncert.nic.in/syllabus.php?ln=en`

### Example

`GET /discover-ncert?syllabus_url=https://ncert.nic.in/syllabus.php?ln=en`

### Success Response

```json
{
  "count": 42,
  "urls": [
    "https://ncert.nic.in/...pdf"
  ]
}
```

---

## 2) Download PDFs

### `POST /fetch-ncert`

Download a provided list of PDF URLs to a local folder.

### Request Body

```json
{
  "urls": ["https://ncert.nic.in/...pdf"],
  "dest_dir": "./ncert_pdfs"
}
```

### Success Response

```json
{
  "downloaded": [
    {
      "url": "https://ncert.nic.in/...pdf",
      "file": "ncert_pdfs/sample.pdf",
      "status": "downloaded",
      "sha256": "..."
    }
  ]
}
```

---

## 3) Process Local PDF Batch

### `POST /process-ncert`

Process PDFs from `pdf_dir`, create JSON outputs, optionally save to Supabase.

### Request Body

```json
{
  "pdf_dir": "./ncert_pdfs",
  "output_dir": "./ncert_json",
  "use_ai": false,
  "save_supabase": true,
  "document_table": "curriculum_sources",
  "section_table": "curriculum_items",
  "fallback_table": "curriculum"
}
```

### Success Response

```json
{
  "processed": 5,
  "details": [
    {
      "file": "ncert_pdfs/desm_s_Chemistry.pdf",
      "status": "processed_supabase",
      "supabase_mode": "normalized_tables",
      "sections_saved": 73,
      "rag_chunks_saved": 120
    }
  ]
}
```

---

## 4) Combined Async Ingestion (Advanced)

### `POST /ingest-ncert`

Runs complete pipeline asynchronously:
- discover URL(s)
- download PDFs
- process curriculum
- save to Supabase
- build RAG index

### Request Body

```json
{
  "syllabus_url": "https://ncert.nic.in/syllabus.php?ln=en",
  "pdf_dir": "./ncert_pdfs",
  "output_dir": "./ncert_json",
  "use_ai": false,
  "save_supabase": true,
  "build_rag": true,
  "rag_index_path": null,
  "document_table": "curriculum_sources",
  "section_table": "curriculum_items",
  "fallback_table": "curriculum"
}
```

### Immediate Response

```json
{
  "job_id": "f7f9f61e-...",
  "status": "queued",
  "message": "NCERT ingestion started"
}
```

Check status using `GET /results/{job_id}`.

---

## 5) Combined Async Ingestion (Simple, One Field)

### `POST /ingest-ncert-simple`

Same as `/ingest-ncert`, but request only needs `syllabus_url`.

### Request Body

```json
{
  "syllabus_url": "https://ncert.nic.in/syllabus.php?ln=en"
}
```

### Immediate Response

```json
{
  "job_id": "dca49b99-...",
  "status": "queued",
  "message": "NCERT ingestion started"
}
```

---

## 6) RAG Query Endpoint

### `POST /rag/query`

Search curriculum index and optionally generate AI answer from top matches.

### Request Body

```json
{
  "query": "What are the Class XI thermodynamics topics?",
  "output_dir": "./ncert_json",
  "rag_index_path": null,
  "top_k": 5,
  "grade": "XI",
  "use_ai": false
}
```

### Success Response

```json
{
  "query": "What are the Class XI thermodynamics topics?",
  "matches": [
    {
      "score": 0.79,
      "source": "ncert_pdfs/desm_s_Chemistry.pdf",
      "grade": "XI",
      "heading": "Unit VI: Thermodynamics",
      "content": "..."
    }
  ],
  "answer": null,
  "index_path": "ncert_json/rag_index.json"
}
```

---

## 7) Upload Single PDF

### `POST /upload-pdf`

Upload one PDF file and parse immediately.

### Request

- `multipart/form-data`
- field: `file`

### Success Response

```json
{
  "job_id": "...",
  "status": "completed",
  "result": {
    "id": "...",
    "source": "...",
    "raw_text_length": 1234,
    "parsed": {"...": "..."},
    "raw_text": "...",
    "ai_summary": null
  }
}
```

---

## 8) Extract Curriculum (Path or Upload)

---

## 9) Download NCERT Grade Books (All Classes/Subjects)

### `POST /download-ncert-grade-books`

Runs asynchronous NCERT textbook scraping and download from `https://ncert.nic.in/textbook.php`:
- iterates every class and subject combination
- selects only one configured item from the 3rd dropdown (default: second item)
- downloads all chapter PDFs for that selected title
- stores files locally under `ncert_pdfs`
- returns app-facing links (`/pdfs/...`) that you can use in your frontend

### Request Body

```json
{
  "textbook_url": "https://ncert.nic.in/textbook.php",
  "dest_dir": "./ncert_pdfs/grade_books",
  "third_dropdown_item": 2,
  "public_base_url": "http://127.0.0.1:8000",
  "save_supabase": false,
  "supabase_table": "ncert_grade_books"
}
```

### Immediate Response

```json
{
  "job_id": "8d4a3fb9-...",
  "status": "queued",
  "message": "NCERT grade books download started",
  "note": "Track progress with GET /results/{job_id}"
}
```

Fetch final result from `GET /results/{job_id}`.

### `POST /extract-curriculum`

Extract curriculum from one PDF using either `file_path` or uploaded `file`.

### Supported Inputs

- Query/Form params:
  - `file_path` (optional)
  - `file` upload (optional)
  - `response_mode` (optional): `ui` (default) or `legacy`
  - `include_raw_text` (optional): `false` default

### UI Mode Response (default)

```json
{
  "job_id": "...",
  "result": {
    "id": "...",
    "source": "...",
    "title": "CHEMISTRY (CLASSES XI –XII)",
    "summary": "...",
    "stats": {
      "raw_text_length": 27364,
      "total_lines": 417,
      "grade_count": 2,
      "section_count": 48
    },
    "grades": [
      {
        "grade": "XI",
        "section_count": 20,
        "sections": [
          {
            "section_id": "XI-1",
            "heading": "Unit I: Some Basic Concepts of Chemistry",
            "points": ["..."],
            "content_preview": "..."
          }
        ]
      }
    ]
  }
}
```

### Legacy Mode Response

Set `response_mode=legacy` to receive original parser payload.

---

## 9) Job Status / Results

### `GET /results/{job_id}`

Return in-memory job/result for ingestion and extraction requests.

### Success Response

```json
{
  "id": "...",
  "status": "completed",
  "stage": "completed",
  "result": {
    "...": "..."
  }
}
```

### Not Found

```json
{
  "detail": "Job not found"
}
```

---

## Supabase Notes

Supabase save can occur in:
- `/process-ncert` (when `save_supabase=true`)
- `/ingest-ncert` (default `save_supabase=true`)
- `/ingest-ncert-simple` (inherits same default)

Default table mapping:
- `document_table`: `curriculum_sources`
- `section_table`: `curriculum_items`
- `fallback_table`: `curriculum`

Required env vars:
- `SUPABASE_URL`
- `SUPABASE_KEY`
- `SUPABASE_CURRICULUM_GROUP_ID` (when schema requires it)

---

## Error Patterns to Watch

- `405 Method Not Allowed`: calling POST endpoints via browser URL bar (GET request)
- `404 PDF directory not found`: wrong `pdf_dir`
- `404 RAG index not found`: run ingestion/process with RAG build first
- Supabase schema errors: table columns/constraints mismatch

---

## Suggested Testing Sequence

1. `POST /ingest-ncert-simple` with one field (`syllabus_url`)
2. `GET /results/{job_id}` until status is `completed`
3. Verify rows in Supabase tables
4. `POST /rag/query` with grade filter
5. `POST /extract-curriculum` and bind `result.grades` in UI
