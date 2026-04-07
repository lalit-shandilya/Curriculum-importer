import argparse
import os
import tempfile
import uuid
from pathlib import Path
from typing import Dict, List, Optional

from fastapi import BackgroundTasks, FastAPI, HTTPException, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import uvicorn

from curriculum_importer import (
    build_ui_curriculum_payload,
    CurriculumParseResult,
    fetch_ncert_pdfs,
    discover_ncert_pdf_urls,
    ingest_ncert_curriculum,
    load_supabase_env_from_registry,
    process_ncert_batch,
    process_pdf,
    query_rag_index,
    resolve_curriculum_group_id,
)

app = FastAPI(title="Curriculum PDF Importer")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

jobs: Dict[str, Dict] = {}


class FetchNcertRequest(BaseModel):
    urls: List[str]
    dest_dir: str = "./ncert_pdfs"


class ProcessNcertRequest(BaseModel):
    pdf_dir: str = "./ncert_pdfs"
    output_dir: str = "./ncert_json"
    use_ai: bool = False
    save_supabase: bool = False
    force_reprocess: bool = False
    document_table: str = "curriculum_sources"
    section_table: str = "curriculum_items"
    fallback_table: str = "curriculum_sources"


class IngestNcertRequest(BaseModel):
    syllabus_url: str
    pdf_dir: str = "./ncert_pdfs"
    output_dir: str = "./ncert_json"
    use_ai: bool = False
    save_supabase: bool = True
    force_reprocess: bool = False
    build_rag: bool = True
    rag_index_path: Optional[str] = None
    document_table: str = "curriculum_sources"
    section_table: str = "curriculum_items"
    fallback_table: str = "curriculum_sources"


class SimpleIngestNcertRequest(BaseModel):
    syllabus_url: str


class RagQueryRequest(BaseModel):
    query: str
    output_dir: str = "./ncert_json"
    rag_index_path: Optional[str] = None
    top_k: int = 5
    grade: Optional[str] = None
    use_ai: bool = False


def _run_ingest_job(job_id: str, request_data: Dict[str, object]) -> None:
    jobs[job_id].update({"status": "running", "stage": "ingesting"})
    try:
        result = ingest_ncert_curriculum(**request_data)
        jobs[job_id].update({"status": "completed", "stage": "completed", "result": result})
    except Exception as exc:
        jobs[job_id].update({"status": "failed", "stage": "failed", "error": str(exc)})


@app.get("/health/supabase")
async def health_supabase():
    try:
        load_supabase_env_from_registry()
        import os
        url = os.getenv("SUPABASE_URL")
        key = os.getenv("SUPABASE_KEY")
        if not url or not key:
            return {"status": "error", "reason": "SUPABASE_URL or SUPABASE_KEY not set"}

        from supabase import create_client
        sb = create_client(url, key)

        tables_ok: Dict[str, bool] = {}
        for table in ["curriculum_groups", "curriculum_sources", "curriculum_items"]:
            try:
                sb.table(table).select("*").limit(1).execute()
                tables_ok[table] = True
            except Exception as exc:
                tables_ok[table] = False

        group_id = None
        group_error = None
        try:
            group_id = resolve_curriculum_group_id(sb)
        except Exception as exc:
            group_error = str(exc)

        # AI provider detection
        ai_providers: Dict[str, Any] = {}
        anthropic_key = os.getenv("ANTHROPIC_API_KEY")
        openai_key = os.getenv("OPENAI_API_KEY")
        ai_providers["anthropic"] = {
            "key_set": bool(anthropic_key),
            "model": os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
        }
        ai_providers["openai"] = {
            "key_set": bool(openai_key),
            "model": os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
        }
        ai_providers["use_ai_ready"] = bool(anthropic_key or openai_key)

        return {
            "status": "ok" if all(tables_ok.values()) and group_id else "degraded",
            "tables": tables_ok,
            "curriculum_group_id": group_id,
            "group_error": group_error,
            "ai": ai_providers,
        }
    except Exception as exc:
        return {"status": "error", "reason": str(exc)}


@app.get("/discover-ncert")
async def discover_ncert(syllabus_url: str = "https://ncert.nic.in/syllabus.php?ln=en"):
    try:
        urls = discover_ncert_pdf_urls(syllabus_url)
        return {"count": len(urls), "urls": urls}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/fetch-ncert")
async def fetch_ncert(req: FetchNcertRequest):
    if not req.urls:
        raise HTTPException(status_code=400, detail="URLs list cannot be empty")

    try:
        result = fetch_ncert_pdfs(req.dest_dir, req.urls)
        return {"downloaded": result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/process-ncert")
async def process_ncert(req: ProcessNcertRequest):
    if not Path(req.pdf_dir).is_dir():
        raise HTTPException(status_code=404, detail=f"PDF directory not found: {req.pdf_dir}")

    try:
        report = process_ncert_batch(
            req.pdf_dir,
            req.output_dir,
            use_ai=req.use_ai,
            save_supabase=req.save_supabase,
            force_reprocess=req.force_reprocess,
            document_table=req.document_table,
            section_table=req.section_table,
            fallback_table=req.fallback_table,
        )
        return {"processed": len(report), "details": report}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/ingest-ncert")
async def ingest_ncert(req: IngestNcertRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    jobs[job_id] = {
        "id": job_id,
        "status": "queued",
        "stage": "queued",
        "request": req.model_dump(),
    }
    background_tasks.add_task(_run_ingest_job, job_id, req.model_dump())
    return {"job_id": job_id, "status": "queued", "message": "NCERT ingestion started"}


@app.post("/ingest-ncert-simple")
async def ingest_ncert_simple(req: SimpleIngestNcertRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    request_data = IngestNcertRequest(syllabus_url=req.syllabus_url, force_reprocess=True).model_dump()
    jobs[job_id] = {
        "id": job_id,
        "status": "queued",
        "stage": "queued",
        "request": request_data,
    }
    background_tasks.add_task(_run_ingest_job, job_id, request_data)
    return {"job_id": job_id, "status": "queued", "message": "NCERT ingestion started"}


@app.post("/rag/query")
async def rag_query(req: RagQueryRequest):
    rag_index_path = req.rag_index_path or str(Path(req.output_dir) / "rag_index.json")
    try:
        result = query_rag_index(
            req.query,
            rag_index_path,
            top_k=req.top_k,
            grade=req.grade,
            use_ai=req.use_ai,
        )
        return result
    except FileNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.post("/upload-pdf")
async def upload_pdf(file: UploadFile = File(...), use_ai: bool = False):
    if not file.filename.lower().endswith(".pdf"):
        raise HTTPException(status_code=400, detail="Only PDF files are accepted")

    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
            content = await file.read()
            tmp.write(content)
            tmp_path = tmp.name

        result = process_pdf(tmp_path, use_ai=use_ai)
        job_id = str(uuid.uuid4())
        jobs[job_id] = {"id": job_id, "status": "completed", "result": result.model_dump()}
        return {"job_id": job_id, "status": "completed", "result": result.model_dump()}
    finally:
        if 'tmp_path' in locals() and os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.post("/extract-curriculum")
async def extract_curriculum(
    file_path: str | None = None,
    file: UploadFile | None = File(None),
    response_mode: str = "ui",
    include_raw_text: bool = False,
    use_ai: bool = False,
):
    if file is None and not file_path:
        raise HTTPException(status_code=400, detail="Either file_path or file upload must be provided")

    tmp_path = None
    try:
        if file is not None:
            if not file.filename.lower().endswith(".pdf"):
                raise HTTPException(status_code=400, detail="Only PDF files are accepted")

            with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                content = await file.read()
                tmp.write(content)
                tmp_path = tmp.name
            file_path = tmp_path

        if not os.path.exists(file_path) or not file_path.lower().endswith(".pdf"):
            raise HTTPException(status_code=404, detail="PDF file not found")

        result = process_pdf(file_path, use_ai=use_ai)
        job_id = str(uuid.uuid4())
        result_payload = result.model_dump() if response_mode == "legacy" else build_ui_curriculum_payload(result, include_raw_text=include_raw_text)
        jobs[job_id] = {"id": job_id, "status": "completed", "result": result_payload}
        return {"job_id": job_id, "result": result_payload}
    finally:
        if tmp_path and os.path.exists(tmp_path):
            os.remove(tmp_path)


@app.get("/results/{job_id}")
async def get_results(job_id: str):
    if job_id not in jobs:
        raise HTTPException(status_code=404, detail="Job not found")
    return jobs[job_id]


def run_api(host="127.0.0.1", port=8000):
    uvicorn.run("main:app", host=host, port=port, reload=True)


def run_script(pdf_path: str):
    if not os.path.exists(pdf_path):
        raise FileNotFoundError(f"PDF not found: {pdf_path}")

    data = process_pdf(pdf_path)
    print("Curriculum extraction completed")
    print("Result:")
    print(data.model_dump())


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Curriculum PDF importer (API + CLI)")
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--api", action="store_true", help="Run FastAPI server")
    group.add_argument("--file", type=str, help="Process single PDF file path")
    group.add_argument("--discover-ncert", action="store_true", help="Discover NCERT PDF URLs automatically")
    group.add_argument("--fetch-ncert", nargs="+", help="Download NCERT PDF URLs to ncert_pdfs")
    group.add_argument("--process-ncert", action="store_true", help="Process PDF files in ncert_pdfs folder")
    parser.add_argument("--ncert-dir", default="./ncert_pdfs", help="NCERT PDF folder")
    parser.add_argument("--output-dir", default="./ncert_json", help="Processed JSON output folder")
    parser.add_argument("--use-ai", action="store_true", help="Enable AI summary step")
    parser.add_argument("--save-supabase", action="store_true", help="Save parsed results to Supabase")
    parser.add_argument("--document-table", default="curriculum_sources", help="Supabase document table")
    parser.add_argument("--section-table", default="curriculum_items", help="Supabase section table")
    parser.add_argument("--fallback-table", default="curriculum_sources", help="Supabase fallback table")
    parser.add_argument("--host", default="127.0.0.1", help="FastAPI host")
    parser.add_argument("--port", default=8000, type=int, help="FastAPI port")

    args = parser.parse_args()
    if args.api:
        run_api(host=args.host, port=args.port)
    elif args.file:
        run_script(args.file)
    elif args.discover_ncert:
        urls = discover_ncert_pdf_urls()
        print(f"Found {len(urls)} NCERT PDFs")
        for u in urls:
            print(u)
    elif args.fetch_ncert:
        result = fetch_ncert_pdfs(args.ncert_dir, args.fetch_ncert)
        print(result)
    elif args.process_ncert:
        result = process_ncert_batch(
            args.ncert_dir,
            args.output_dir,
            use_ai=args.use_ai,
            save_supabase=args.save_supabase,
            document_table=args.document_table,
            section_table=args.section_table,
            fallback_table=args.fallback_table,
        )
        print(result)
    else:
        parser.print_help()
