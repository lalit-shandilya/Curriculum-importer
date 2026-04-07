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
- `GET /results/{job_id}`

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
