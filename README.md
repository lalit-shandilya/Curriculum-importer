# Curriculum PDF Importer

A minimal FastAPI app + CLI for importing and parsing curriculum PDFs.

## Setup

```powershell
cd E:\BM\Curriculum-importer
python -m pip install -r requirements.txt
```

## Run as API

```powershell
python main.py --api --host 127.0.0.1 --port 8000
```

Open docs
- http://127.0.0.1:8000/docs
- http://127.0.0.1:8000/redoc

## Run as CLI

```powershell
python main.py --file "C:\path\to\your.pdf"
```

## Endpoints

- `POST /upload-pdf` (multipart PDF)
- `POST /extract-curriculum` (json `{ "file_path": "..." }`)
- `POST /download-ncert-grade-books` (async NCERT textbook downloader)
- `GET /results/{job_id}`

Downloaded NCERT PDFs are exposed from this API at:
- `GET /pdfs/...`

Example app-facing URL format:
- `http://127.0.0.1:8000/pdfs/grade_books/class_i/english/aemr/aemr01.pdf`

## Download NCERT Grade Books

This endpoint iterates all class + subject combinations from `https://ncert.nic.in/textbook.php`, picks only the configured item from the 3rd dropdown (default: second item), and downloads all chapter PDFs for that selected title.

```powershell
curl -X POST "http://127.0.0.1:8000/download-ncert-grade-books" `
	-H "Content-Type: application/json" `
	-d '{
		"textbook_url": "https://ncert.nic.in/textbook.php",
		"dest_dir": "./ncert_pdfs/grade_books",
		"third_dropdown_item": 2,
		"public_base_url": "http://127.0.0.1:8000",
		"save_supabase": false,
		"supabase_table": "ncert_grade_books"
	}'
```

Track progress using `GET /results/{job_id}` from the response.

## Restart / Troubleshooting

If Swagger (`/docs`) or endpoints are not accessible after starting the server, stale Python processes may still be holding the port.

**Stop all Python processes and restart cleanly:**

```powershell
# Kill every Python process
Get-Process python -ErrorAction SilentlyContinue | Stop-Process -Force

# Confirm port 8000 is free (should return empty)
netstat -ano | findstr ":8000 " | findstr "LISTENING"

# Start fresh
cd E:\BM\Curriculum-importer
e:\BM\Curriculum-importer\.venv\Scripts\python.exe -m uvicorn main:app --host 127.0.0.1 --port 8000 --reload
```

> **Why this happens:** `python main.py --api` launches uvicorn with `reload=True`, which spawns a watcher child process. If the parent is killed abruptly, the child can keep the port bound even though it is no longer responding.

## Test

```powershell
pip install pytest httpx
pytest -q
```

## Docker

```bash
docker build -t curriculum-importer .
docker run -p 8000:8000 curriculum-importer
```
