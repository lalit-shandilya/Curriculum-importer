import os
import json
import uuid
from fastapi.testclient import TestClient
from curriculum_importer import CurriculumParseResult
from main import app

client = TestClient(app)


def test_docs_accessible():
    response = client.get("/docs")
    assert response.status_code in (200, 307)


def test_discover_ncert_handles_error():
    response = client.get("/discover-ncert", params={"syllabus_url": "https://ncert.nic.in/syllabus.php?ln=en"})
    assert response.status_code in (200, 500)
    data = response.json()
    assert "count" in data or "detail" in data


def test_fetch_ncert_invalid_payload():
    response = client.post("/fetch-ncert", json={})
    assert response.status_code == 422


def test_process_ncert_missing_dir():
    response = client.post("/process-ncert", json={"pdf_dir": "./nonexistent_folder", "output_dir": "./tmp"})
    assert response.status_code == 404


def test_extract_curriculum_missing_file():
    response = client.post("/extract-curriculum", params={"file_path": "C:/does/not/exist.pdf"})
    assert response.status_code == 404


def test_extract_curriculum_ui_mode_default(monkeypatch):
    fake = {
        "id": str(uuid.uuid4()),
        "source": "sample.pdf",
        "raw_text_length": 100,
        "parsed": {
            "total_lines": 4,
            "title": "Chemistry",
            "grades": [
                {
                    "grade": "XI",
                    "sections": [
                        {"heading": "Unit I", "content": ["Atoms", "Molecules"]},
                    ],
                }
            ],
        },
        "raw_text": "Chemistry\nUnit I",
        "ai_summary": "Short summary",
    }

    monkeypatch.setattr("main.os.path.exists", lambda p: True)
    monkeypatch.setattr("main.process_pdf", lambda p, use_ai=False: CurriculumParseResult(**fake))

    response = client.post("/extract-curriculum", params={"file_path": "C:/mock.pdf"})
    assert response.status_code == 200
    body = response.json()
    assert "job_id" in body
    assert body["result"]["title"] == "Chemistry"
    assert "grades" in body["result"]
    assert "stats" in body["result"]
    assert body["result"]["grades"][0]["sections"][0]["heading"] == "Unit I"


def test_extract_curriculum_legacy_mode(monkeypatch):
    fake = {
        "id": str(uuid.uuid4()),
        "source": "sample.pdf",
        "raw_text_length": 100,
        "parsed": {"total_lines": 2, "title": "Biology", "sections": []},
        "raw_text": "Raw",
        "ai_summary": None,
    }

    monkeypatch.setattr("main.os.path.exists", lambda p: True)
    monkeypatch.setattr("main.process_pdf", lambda p, use_ai=False: CurriculumParseResult(**fake))

    response = client.post(
        "/extract-curriculum",
        params={"file_path": "C:/mock.pdf", "response_mode": "legacy"},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["result"]["raw_text"] == "Raw"
    assert body["result"]["parsed"]["title"] == "Biology"


def test_ingest_ncert_runs_background_job(monkeypatch, tmp_path):
    def fake_ingest(**kwargs):
        return {
            "syllabus_url": kwargs["syllabus_url"],
            "download_report": [],
            "process_report": [{"file": "sample.pdf", "status": "processed_supabase"}],
            "rag_index_path": str(tmp_path / "rag_index.json"),
        }

    monkeypatch.setattr("main.ingest_ncert_curriculum", fake_ingest)

    response = client.post(
        "/ingest-ncert",
        json={"syllabus_url": "https://ncert.nic.in/syllabus.php?ln=en"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"

    result_response = client.get(f"/results/{body['job_id']}")
    assert result_response.status_code == 200
    result_body = result_response.json()
    assert result_body["status"] == "completed"
    assert result_body["result"]["process_report"][0]["status"] == "processed_supabase"


def test_ingest_ncert_simple_runs_background_job(monkeypatch, tmp_path):
    def fake_ingest(**kwargs):
        return {
            "syllabus_url": kwargs["syllabus_url"],
            "download_report": [],
            "process_report": [{"file": "sample.pdf", "status": "processed_supabase"}],
            "rag_index_path": str(tmp_path / "rag_index.json"),
        }

    monkeypatch.setattr("main.ingest_ncert_curriculum", fake_ingest)

    response = client.post(
        "/ingest-ncert-simple",
        json={"syllabus_url": "https://ncert.nic.in/syllabus.php?ln=en"},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"

    result_response = client.get(f"/results/{body['job_id']}")
    assert result_response.status_code == 200
    result_body = result_response.json()
    assert result_body["status"] == "completed"
    assert result_body["request"]["pdf_dir"] == "./ncert_pdfs"
    assert result_body["request"]["output_dir"] == "./ncert_json"


def test_download_ncert_grade_books_runs_background_job(monkeypatch):
    def fake_download(**kwargs):
        return {
            "textbook_url": kwargs["textbook_url"],
            "books_considered": 1,
            "pdfs_downloaded": 2,
            "books": [
                {
                    "class": "Class I",
                    "subject": "English",
                    "book_title": "Second Book",
                    "status": "completed",
                    "files": [
                        {
                            "app_pdf_url": "/pdfs/grade_books/class_i/english/aemr/aemr01.pdf",
                            "status": "downloaded",
                        }
                    ],
                }
            ],
        }

    monkeypatch.setattr("main.download_ncert_grade_books", fake_download)

    response = client.post(
        "/download-ncert-grade-books",
        json={"textbook_url": "https://ncert.nic.in/textbook.php", "third_dropdown_item": 2},
    )

    assert response.status_code == 200
    body = response.json()
    assert body["status"] == "queued"

    result_response = client.get(f"/results/{body['job_id']}")
    assert result_response.status_code == 200
    result_body = result_response.json()
    assert result_body["status"] == "completed"
    assert result_body["result"]["pdfs_downloaded"] == 2


def test_rag_query_reads_index(tmp_path):
    rag_index_path = tmp_path / "rag_index.json"
    rag_index_path.write_text(
        json.dumps(
            [
                {
                    "id": "1",
                    "document_id": "doc-1",
                    "source": "chemistry.pdf",
                    "title": "Chemistry",
                    "grade": "XI",
                    "heading": "Unit I",
                    "chunk_index": 1,
                    "content": "Atoms molecules stoichiometry and chemical reactions.",
                    "embedding": [1.0, 0.0, 0.0],
                },
                {
                    "id": "2",
                    "document_id": "doc-2",
                    "source": "biology.pdf",
                    "title": "Biology",
                    "grade": "XII",
                    "heading": "Unit II",
                    "chunk_index": 1,
                    "content": "Genetics evolution and reproduction.",
                    "embedding": [0.0, 1.0, 0.0],
                },
            ]
        ),
        encoding="utf-8",
    )

    response = client.post(
        "/rag/query",
        json={
            "query": "chemical reactions atoms",
            "rag_index_path": str(rag_index_path),
            "top_k": 1,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert len(body["matches"]) == 1
    assert body["matches"][0]["source"] == "chemistry.pdf"
