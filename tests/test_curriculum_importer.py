import json

from curriculum_importer import (
    CurriculumParseResult,
    _build_curriculum_item_rows,
    _grade_to_int,
    _save_to_curriculum_schema,
    _upsert_curriculum_items,
    parse_curriculum,
    process_ncert_batch,
)


def test_parse_curriculum_moves_general_into_first_specific_grade():
    raw_text = """Sample Curriculum
General intro line
CLASS XI
Unit I:
Topic A
CLASS XII
Unit II:
Topic B
"""

    parsed = parse_curriculum(raw_text)
    grades = parsed.get("grades", [])

    grade_labels = [g.get("grade") for g in grades]
    assert "general" not in grade_labels
    assert grade_labels[0] == "XI"


def test_parse_curriculum_extracts_grade_from_syllabus_of_class_heading():
    raw_text = """Sample Curriculum
PARTIAL OCR TEXT SYLLABUS OF CLASS XI
Unit I:
Topic A
BROKEN HEADER SYLLABUS OF CLASS XII
Unit II:
Topic B
"""

    parsed = parse_curriculum(raw_text)
    grade_labels = [g.get("grade") for g in parsed.get("grades", [])]

    assert grade_labels == ["XI", "XII"]


def test_grade_to_int_parses_noisy_syllabus_grade_label():
    assert _grade_to_int("PARTIAL OCR SYLLABUS OF CLASS XI") == 11



def test_build_rows_does_not_emit_grade_zero_for_mixed_grade_documents():
    parsed = {
        "title": "Chemistry",
        "grades": [
            {"grade": "general", "sections": [{"heading": "Intro", "content": ["line 1"]}]},
            {"grade": "XI", "sections": [{"heading": "Unit 1", "content": ["a"]}]},
            {"grade": "XII", "sections": [{"heading": "Unit 2", "content": ["b"]}]},
        ],
    }

    rows = _build_curriculum_item_rows(parsed, "gid", "sid")
    grades = {row["grade"] for row in rows}

    assert 0 not in grades
    assert 11 in grades
    assert 12 in grades


def test_process_batch_reprocesses_manifest_hit_when_supabase_record_missing(monkeypatch, tmp_path):
    pdf_dir = tmp_path / "pdfs"
    output_dir = tmp_path / "out"
    pdf_dir.mkdir()
    output_dir.mkdir()
    pdf_path = pdf_dir / "sample.pdf"
    pdf_path.write_bytes(b"pdf")

    processed_manifest = {str(pdf_path): {"sha256": "same-hash", "processed_at": 1}}
    (output_dir / "processed_manifest.json").write_text(json.dumps(processed_manifest), encoding="utf-8")

    fake_result = CurriculumParseResult(
        id="doc-1",
        source=str(pdf_path),
        raw_text_length=10,
        parsed={"title": "Chemistry", "total_lines": 1, "grades": []},
        raw_text="text",
        ai_summary=None,
    )

    monkeypatch.setattr("curriculum_importer.compute_file_hash", lambda _: "same-hash")
    monkeypatch.setattr("curriculum_importer._curriculum_record_exists_in_supabase", lambda *args, **kwargs: False)
    monkeypatch.setattr("curriculum_importer.process_pdf", lambda *args, **kwargs: fake_result)
    monkeypatch.setattr(
        "curriculum_importer.save_curriculum_to_supabase",
        lambda *args, **kwargs: {"mode": "normalized_tables", "sections_saved": 3},
    )

    report = process_ncert_batch(str(pdf_dir), str(output_dir), save_supabase=True)

    assert len(report) == 1
    assert report[0]["status"] == "processed_supabase"
    assert report[0]["reprocessed_from_manifest"] is True


def test_process_batch_skips_manifest_hit_when_supabase_record_exists(monkeypatch, tmp_path):
    pdf_dir = tmp_path / "pdfs"
    output_dir = tmp_path / "out"
    pdf_dir.mkdir()
    output_dir.mkdir()
    pdf_path = pdf_dir / "sample.pdf"
    pdf_path.write_bytes(b"pdf")

    processed_manifest = {str(pdf_path): {"sha256": "same-hash", "processed_at": 1}}
    (output_dir / "processed_manifest.json").write_text(json.dumps(processed_manifest), encoding="utf-8")

    monkeypatch.setattr("curriculum_importer.compute_file_hash", lambda _: "same-hash")
    monkeypatch.setattr("curriculum_importer._curriculum_record_exists_in_supabase", lambda *args, **kwargs: True)

    def fail_process(*args, **kwargs):
        raise AssertionError("process_pdf should not be called when manifest and Supabase both have the record")

    monkeypatch.setattr("curriculum_importer.process_pdf", fail_process)

    report = process_ncert_batch(str(pdf_dir), str(output_dir), save_supabase=True)

    assert len(report) == 1
    assert report[0]["status"] == "already_processed"


def test_save_to_curriculum_schema_reuses_existing_source(monkeypatch):
    deleted = []

    fake_result = CurriculumParseResult(
        id="doc-1",
        source="ncert_pdfs/sample.pdf",
        raw_text_length=10,
        parsed={
            "title": "Chemistry",
            "total_lines": 3,
            "grades": [{"grade": "XI", "sections": [{"heading": "Intro", "content": ["line 1"]}]}],
        },
        raw_text="raw",
        ai_summary=None,
    )

    monkeypatch.setattr(
        "curriculum_importer._find_existing_curriculum_source",
        lambda *args, **kwargs: {"source_id": "source-1"},
    )
    monkeypatch.setattr(
        "curriculum_importer._update_with_column_adaptation",
        lambda *args, **kwargs: {"updated": True},
    )
    monkeypatch.setattr(
        "curriculum_importer._delete_curriculum_items_for_source",
        lambda _supabase, source_id: deleted.append(source_id),
    )
    monkeypatch.setattr(
        "curriculum_importer._upsert_curriculum_items",
        lambda *args, **kwargs: {"inserted": 1, "updated": 0},
    )

    out = _save_to_curriculum_schema(object(), fake_result, "group-1")

    assert out["source_id"] == "source-1"
    assert out["source_action"] == "updated"
    assert deleted == ["source-1"]


def test_upsert_curriculum_items_updates_on_duplicate(monkeypatch):
    calls = {"insert": 0, "update": 0}
    row = {
        "curriculum_group_id": "group-1",
        "source_id": "source-1",
        "grade": 11,
        "subject": "CHEMISTRY",
        "lesson_title": "Introduction",
        "description": "desc",
    }

    def fake_insert(*args, **kwargs):
        calls["insert"] += 1
        raise RuntimeError("duplicate key value violates unique constraint 'uq_curriculum_items_identity'")

    def fake_find(*args, **kwargs):
        return {"id": "item-1"}

    def fake_update(*args, **kwargs):
        calls["update"] += 1
        return {"updated": True}

    monkeypatch.setattr("curriculum_importer._insert_with_column_adaptation", fake_insert)
    monkeypatch.setattr("curriculum_importer._find_existing_curriculum_item", fake_find)
    monkeypatch.setattr("curriculum_importer._update_with_column_adaptation", fake_update)

    out = _upsert_curriculum_items(object(), [row])

    assert calls == {"insert": 1, "update": 1}
    assert out == {"inserted": 0, "updated": 1}
