import hashlib
import json
import math
import os
import re
import time
import uuid
from collections import Counter
from pathlib import Path
from typing import Any, Dict, List, Optional

import pdfplumber
import requests
from bs4 import BeautifulSoup
from pydantic import BaseModel

try:
    import pypdfium2
except ImportError:
    pypdfium2 = None

try:
    import pytesseract
except ImportError:
    pytesseract = None

try:
    from supabase import create_client
except ImportError:
    create_client = None

try:
    import openai
except ImportError:
    openai = None

try:
    import winreg
except ImportError:
    winreg = None

try:
    from anthropic import Anthropic
except ImportError:
    Anthropic = None


LOCAL_EMBEDDING_DIMENSIONS = 256
DEFAULT_RAG_CHUNK_WORDS = 180
DEFAULT_RAG_OVERLAP_WORDS = 40


def load_supabase_env_from_registry() -> None:
    # Helpful on Windows when vars are set at user-level but server wasn't restarted.
    if winreg is None:
        return
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, r"Environment") as key:
            for name in [
                "SUPABASE_URL",
                "SUPABASE_KEY",
                "SUPABASE_CURRICULUM_GROUP_ID",
                "ANTHROPIC_API_KEY",
                "OPENAI_API_KEY",
                "ANTHROPIC_MODEL",
                "OPENAI_MODEL",
            ]:
                if os.getenv(name):
                    continue
                try:
                    os.environ[name] = winreg.QueryValueEx(key, name)[0]
                except FileNotFoundError:
                    continue
    except OSError:
        return


def resolve_curriculum_group_id(supabase: Any) -> str:
    env_group_id = os.getenv("SUPABASE_CURRICULUM_GROUP_ID")
    if env_group_id:
        return env_group_id

    existing = supabase.table("curriculum_groups").select("id").limit(1).execute()
    existing_rows = existing.data or []
    if existing_rows:
        group_id = str(existing_rows[0].get("id"))
        os.environ["SUPABASE_CURRICULUM_GROUP_ID"] = group_id
        return group_id

    uid = str(uuid.uuid4())
    payload = {
        "id": uid,
        "code": f"AUTO-GROUP-{uid[:8]}",
        "name": "Auto Curriculum Group",
        "country_code": "IN",
        "status": "active",
        "description": "Auto-created by curriculum importer",
    }

    response = _insert_with_column_adaptation(supabase, "curriculum_groups", payload)
    rows = response.data or []
    if not rows:
        raise RuntimeError("Failed to create or fetch curriculum group id")

    group_id = str(rows[0].get("id"))
    if not group_id:
        raise RuntimeError("Curriculum group insert succeeded but id was missing in response")

    os.environ["SUPABASE_CURRICULUM_GROUP_ID"] = group_id
    return group_id


def _extract_anthropic_text(response: Any) -> str:
    parts = []
    for block in getattr(response, "content", []):
        if getattr(block, "type", None) == "text":
            parts.append(block.text)
    return "\n".join(part.strip() for part in parts if part and part.strip()).strip()


def generate_llm_text(system_prompt: str, user_prompt: str, max_tokens: int = 400) -> str:
    errors: List[str] = []
    anthropic_key = os.getenv("ANTHROPIC_API_KEY")
    if Anthropic is not None and anthropic_key:
        try:
            client = Anthropic(api_key=anthropic_key)
            response = client.messages.create(
                model=os.getenv("ANTHROPIC_MODEL", "claude-3-5-sonnet-latest"),
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
                max_tokens=max_tokens,
            )
            text = _extract_anthropic_text(response)
            if text:
                return text
            errors.append("Anthropic returned empty response")
        except Exception as exc:
            errors.append(f"Anthropic error: {exc}")

    openai_key = os.getenv("OPENAI_API_KEY")
    if openai is not None and openai_key:
        try:
            if hasattr(openai, "OpenAI"):
                client = openai.OpenAI(api_key=openai_key)
                response = client.chat.completions.create(
                    model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": user_prompt},
                    ],
                    max_tokens=max_tokens,
                    temperature=0.2,
                )
                return response.choices[0].message.content.strip()

            openai.api_key = openai_key
            response = openai.ChatCompletion.create(
                model=os.getenv("OPENAI_MODEL", "gpt-3.5-turbo"),
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
                max_tokens=max_tokens,
                temperature=0.2,
            )
            return response.choices[0].message.content.strip()
        except Exception as exc:
            errors.append(f"OpenAI error: {exc}")

    if errors:
        raise RuntimeError("; ".join(errors))

    raise RuntimeError("No supported LLM provider configured. Set ANTHROPIC_API_KEY or OPENAI_API_KEY.")


def create_ai_summary(text: str, max_tokens: int = 200) -> str:
    prompt = (
        "You are a curriculum parsing assistant. "
        "Summarize the following curriculum text into a concise structured summary, "
        "including title, number of sections and short topics.\n\n" + text
    )

    try:
        return generate_llm_text(
            "You are a helpful assistant that summarizes curriculum text.",
            prompt,
            max_tokens=max_tokens,
        )
    except Exception as exc:
        raise RuntimeError(f"AI summary generation failed: {exc}")


class CurriculumSection(BaseModel):
    heading: str
    content: List[str]


class CurriculumParseResult(BaseModel):
    id: str
    source: str
    raw_text_length: int
    parsed: Dict[str, Any]
    raw_text: str
    ai_summary: Optional[str] = None


class SupabaseResult(BaseModel):
    status: str
    data: Any


def build_ui_curriculum_payload(result: CurriculumParseResult, include_raw_text: bool = False) -> Dict[str, Any]:
    parsed = result.parsed or {}
    title = parsed.get("title", "")
    grades = parsed.get("grades", [])

    normalized_grades: List[Dict[str, Any]] = []
    total_sections = 0
    for grade_bucket in grades:
        grade_label = str(grade_bucket.get("grade", "general"))
        sections = []
        for index, section in enumerate(grade_bucket.get("sections", []), start=1):
            lines = [str(line).strip() for line in section.get("content", []) if str(line).strip()]
            total_sections += 1
            sections.append(
                {
                    "section_id": f"{grade_label}-{index}",
                    "heading": str(section.get("heading", "")).strip(),
                    "points": lines,
                    "content_preview": " ".join(lines[:3])[:280],
                }
            )

        normalized_grades.append(
            {
                "grade": grade_label,
                "section_count": len(sections),
                "sections": sections,
            }
        )

    payload = {
        "id": result.id,
        "source": result.source,
        "title": title,
        "summary": result.ai_summary,
        "stats": {
            "raw_text_length": result.raw_text_length,
            "total_lines": int(parsed.get("total_lines", 0) or 0),
            "grade_count": len(normalized_grades),
            "section_count": total_sections,
        },
        "grades": normalized_grades,
    }

    if include_raw_text:
        payload["raw_text"] = result.raw_text

    return payload


_CLASS_HEADING_RE = re.compile(r"^\s*CLASS\s*[-:]*\s*(?:([IVXLC]+)|(\d{1,2}))\b", re.IGNORECASE)
_SYLLABUS_CLASS_HEADING_RE = re.compile(
    r"^\s*(?:[A-Z0-9&(),./'\- ]{0,120}\s+)?SYLLABUS\s+OF\s+CLASS(?:ES)?\s*[-:]*\s*(?:([IVXLC]+)|(\d{1,2}))\b",
    re.IGNORECASE,
)
_SECTION_HEADING_RE = re.compile(r"^\s*(Unit\s+[IVXLC]+\b.*|Module\s+\d+\b.*)", re.IGNORECASE)


def _is_probable_page_number(line: str) -> bool:
    token = line.strip()
    return token.isdigit() and len(token) <= 3


def _normalize_text_lines(raw_text: str) -> List[str]:
    lines = []
    for raw_line in raw_text.splitlines():
        line = raw_line.strip()
        if not line:
            continue
        if _is_probable_page_number(line):
            continue
        lines.append(line)
    return lines


def _empty_grade_bucket(grade: str) -> Dict[str, Any]:
    return {"grade": grade, "sections": []}


def _append_section(bucket: Dict[str, Any], section: Optional[Dict[str, Any]]) -> None:
    if section and section.get("heading"):
        bucket["sections"].append(section)


def _grade_to_int(grade: str) -> Optional[int]:
    text = str(grade).strip().upper()
    if not text:
        return None

    # Recover class labels from noisy grade strings like
    # "... SYLLABUS OF CLASS XI" before numeric conversion.
    embedded_class = re.search(r"\bCLASS(?:ES)?\s*[-:]*\s*([IVXLC]+|\d{1,2})\b", text)
    if embedded_class:
        text = embedded_class.group(1).upper()

    if text.isdigit():
        return int(text)

    roman_values = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100}
    total = 0
    prev = 0
    for ch in reversed(text):
        if ch not in roman_values:
            return None
        val = roman_values[ch]
        if val < prev:
            total -= val
        else:
            total += val
            prev = val
    return total if total > 0 else None


def _insert_with_column_adaptation(supabase: Any, table: str, payload: Any) -> Any:
    # Remove unknown columns reported by PostgREST and retry with remaining fields.
    attempts = 0
    while attempts < 30:
        attempts += 1
        try:
            return supabase.table(table).insert(payload).execute()
        except Exception as exc:
            msg = str(exc)
            missing = re.search(r"Could not find the '([^']+)' column", msg)
            if not missing:
                raise

            missing_col = missing.group(1)
            if isinstance(payload, list):
                removed_any = False
                for row in payload:
                    if isinstance(row, dict) and missing_col in row:
                        row.pop(missing_col, None)
                        removed_any = True
                if not removed_any:
                    raise
            elif isinstance(payload, dict):
                if missing_col not in payload:
                    raise
                payload.pop(missing_col, None)
            else:
                raise

    raise RuntimeError(f"Failed to adapt payload for table '{table}' after repeated attempts")


def _update_with_column_adaptation(supabase: Any, table: str, payload: Dict[str, Any], match_column: str, match_value: Any) -> Any:
    attempts = 0
    while attempts < 30:
        attempts += 1
        try:
            return supabase.table(table).update(payload).eq(match_column, match_value).execute()
        except Exception as exc:
            msg = str(exc)
            missing = re.search(r"Could not find the '([^']+)' column", msg)
            if not missing:
                raise

            missing_col = missing.group(1)
            if missing_col not in payload:
                raise
            payload.pop(missing_col, None)

    raise RuntimeError(f"Failed to adapt update payload for table '{table}' after repeated attempts")


def _find_existing_curriculum_source(supabase: Any, curriculum_group_id: str, source_name: str, source_url: str) -> Optional[Dict[str, Any]]:
    candidates: List[Dict[str, Any]] = []
    for column, value in [("source_name", source_name), ("source_url", source_url)]:
        try:
            rows = (
                supabase.table("curriculum_sources")
                .select("source_id,curriculum_group_id,source_name,source_url,created_at")
                .eq("curriculum_group_id", curriculum_group_id)
                .eq(column, value)
                .limit(20)
                .execute()
                .data
                or []
            )
            candidates.extend(rows)
        except Exception:
            continue

    unique_candidates: Dict[str, Dict[str, Any]] = {}
    for row in candidates:
        source_id = row.get("source_id") or row.get("id")
        if source_id:
            unique_candidates[str(source_id)] = row

    if not unique_candidates:
        return None

    return sorted(
        unique_candidates.values(),
        key=lambda row: str(row.get("created_at") or ""),
        reverse=True,
    )[0]


def _delete_curriculum_items_for_source(supabase: Any, source_id: str) -> None:
    try:
        supabase.table("curriculum_items").delete().eq("source_id", source_id).execute()
    except Exception:
        return


def _find_existing_curriculum_item(supabase: Any, row: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    try:
        matches = (
            supabase.table("curriculum_items")
            .select("id,source_id,lesson_title,unit_no,lesson_no")
            .eq("curriculum_group_id", row.get("curriculum_group_id"))
            .eq("grade", row.get("grade"))
            .eq("subject", row.get("subject"))
            .ilike("lesson_title", str(row.get("lesson_title", "")))
            .limit(20)
            .execute()
            .data
            or []
        )
    except Exception:
        return None

    target_unit_no = row.get("unit_no")
    target_lesson_no = row.get("lesson_no")
    target_lesson_title = str(row.get("lesson_title", "")).strip().lower()

    for match in matches:
        if str(match.get("lesson_title", "")).strip().lower() != target_lesson_title:
            continue
        if match.get("unit_no") != target_unit_no:
            continue
        if match.get("lesson_no") != target_lesson_no:
            continue
        return match

    return None


def _upsert_curriculum_items(supabase: Any, item_rows: List[Dict[str, Any]]) -> Dict[str, Any]:
    inserted = 0
    updated = 0

    for row in item_rows:
        try:
            _insert_with_column_adaptation(supabase, "curriculum_items", dict(row))
            inserted += 1
        except Exception as exc:
            if "uq_curriculum_items_identity" not in str(exc) and "duplicate key value violates unique constraint" not in str(exc):
                raise

            existing_item = _find_existing_curriculum_item(supabase, row)
            if not existing_item:
                raise

            payload = dict(row)
            payload.pop("curriculum_group_id", None)
            _update_with_column_adaptation(supabase, "curriculum_items", payload, "id", existing_item["id"])
            updated += 1

    return {"inserted": inserted, "updated": updated}


def _tokenize(text: str) -> List[str]:
    return re.findall(r"[a-z0-9]+", text.lower())


def create_local_embedding(text: str, dimensions: int = LOCAL_EMBEDDING_DIMENSIONS) -> List[float]:
    vector = [0.0] * dimensions
    counts = Counter(_tokenize(text))
    if not counts:
        return vector

    for token, count in counts.items():
        digest = hashlib.sha256(token.encode("utf-8")).digest()
        index = int.from_bytes(digest[:4], "big") % dimensions
        sign = 1.0 if digest[4] % 2 == 0 else -1.0
        vector[index] += sign * float(count)

    norm = math.sqrt(sum(value * value for value in vector))
    if norm == 0:
        return vector
    return [value / norm for value in vector]


def cosine_similarity(vector_a: List[float], vector_b: List[float]) -> float:
    if not vector_a or not vector_b or len(vector_a) != len(vector_b):
        return 0.0
    return sum(a * b for a, b in zip(vector_a, vector_b))


def _split_words(text: str, chunk_words: int, overlap_words: int) -> List[str]:
    words = text.split()
    if not words:
        return []

    if len(words) <= chunk_words:
        return [text]

    chunks = []
    start = 0
    step = max(1, chunk_words - overlap_words)
    while start < len(words):
        chunk = words[start:start + chunk_words]
        if not chunk:
            break
        chunks.append(" ".join(chunk))
        if start + chunk_words >= len(words):
            break
        start += step
    return chunks


def build_rag_chunks(
    result: CurriculumParseResult,
    chunk_words: int = DEFAULT_RAG_CHUNK_WORDS,
    overlap_words: int = DEFAULT_RAG_OVERLAP_WORDS,
) -> List[Dict[str, Any]]:
    parsed = result.parsed or {}
    title = parsed.get("title", "")
    grades = parsed.get("grades") or [{"grade": "general", "sections": parsed.get("sections", [])}]
    chunks: List[Dict[str, Any]] = []

    for grade_bucket in grades:
        grade = str(grade_bucket.get("grade", "general"))
        for section in grade_bucket.get("sections", []):
            heading = section.get("heading", "")
            content_text = "\n".join(section.get("content", []))
            section_text = "\n".join(part for part in [title, f"Grade {grade}", heading, content_text] if part).strip()
            for chunk_index, chunk_text in enumerate(_split_words(section_text, chunk_words, overlap_words), start=1):
                chunks.append(
                    {
                        "id": str(uuid.uuid4()),
                        "document_id": result.id,
                        "source": result.source,
                        "title": title,
                        "grade": grade,
                        "heading": heading,
                        "chunk_index": chunk_index,
                        "content": chunk_text,
                        "embedding": create_local_embedding(chunk_text),
                    }
                )
    return chunks


def update_rag_index(
    result: CurriculumParseResult,
    index_path: str,
    chunk_words: int = DEFAULT_RAG_CHUNK_WORDS,
    overlap_words: int = DEFAULT_RAG_OVERLAP_WORDS,
) -> Dict[str, Any]:
    path = Path(index_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    if path.exists():
        with open(path, "r", encoding="utf-8") as f:
            existing = json.load(f)
    else:
        existing = []

    existing = [chunk for chunk in existing if chunk.get("source") != result.source]
    new_chunks = build_rag_chunks(result, chunk_words=chunk_words, overlap_words=overlap_words)
    existing.extend(new_chunks)

    with open(path, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

    return {"index_path": str(path), "chunks_saved": len(new_chunks), "indexed_documents": len({chunk.get('source') for chunk in existing})}


def query_rag_index(
    query: str,
    index_path: str,
    top_k: int = 5,
    grade: Optional[str] = None,
    use_ai: bool = False,
) -> Dict[str, Any]:
    path = Path(index_path)
    if not path.exists():
        raise FileNotFoundError(f"RAG index not found: {index_path}")

    with open(path, "r", encoding="utf-8") as f:
        chunks = json.load(f)

    if grade is not None:
        grade_text = str(grade).strip().upper()
        chunks = [chunk for chunk in chunks if str(chunk.get("grade", "")).strip().upper() == grade_text]

    query_embedding = create_local_embedding(query)
    query_tokens = set(_tokenize(query))
    scored_matches = []
    for chunk in chunks:
        score = cosine_similarity(query_embedding, chunk.get("embedding", []))
        content_tokens = set(_tokenize(chunk.get("content", "")))
        if query_tokens and content_tokens:
            score += 0.1 * (len(query_tokens & content_tokens) / len(query_tokens))
        if score <= 0:
            continue
        scored_matches.append(
            {
                "score": round(score, 4),
                "document_id": chunk.get("document_id"),
                "source": chunk.get("source"),
                "title": chunk.get("title"),
                "grade": chunk.get("grade"),
                "heading": chunk.get("heading"),
                "chunk_index": chunk.get("chunk_index"),
                "content": chunk.get("content"),
            }
        )

    scored_matches.sort(key=lambda item: item["score"], reverse=True)
    matches = scored_matches[:top_k]

    answer = None
    if use_ai and matches:
        context = "\n\n".join(
            f"Source: {match['source']} | Grade: {match['grade']} | Heading: {match['heading']}\n{match['content']}"
            for match in matches
        )
        prompt = (
            "Answer the question using only the provided curriculum context. "
            "If the answer is not in the context, say so clearly.\n\n"
            f"Question: {query}\n\nContext:\n{context}"
        )
        answer = generate_llm_text(
            "You answer questions strictly from provided curriculum excerpts.",
            prompt,
            max_tokens=500,
        )

    return {"query": query, "matches": matches, "answer": answer, "index_path": str(path)}


def resolve_ncert_urls(syllabus_url: str) -> List[str]:
    if syllabus_url.lower().endswith(".pdf"):
        return [syllabus_url]
    return discover_ncert_pdf_urls(syllabus_url)


def ingest_ncert_curriculum(
    syllabus_url: str,
    pdf_dir: str,
    output_dir: str,
    use_ai: bool = False,
    save_supabase: bool = True,
    force_reprocess: bool = False,
    build_rag: bool = True,
    rag_index_path: Optional[str] = None,
    document_table: str = "curriculum_sources",
    section_table: str = "curriculum_items",
    fallback_table: str = "curriculum_sources",
) -> Dict[str, Any]:
    urls = resolve_ncert_urls(syllabus_url)
    download_report = fetch_ncert_pdfs(pdf_dir, urls)
    effective_rag_index = rag_index_path or str(Path(output_dir) / "rag_index.json")
    process_report = process_ncert_batch(
        pdf_dir,
        output_dir,
        use_ai=use_ai,
        save_supabase=save_supabase,
        force_reprocess=force_reprocess,
        document_table=document_table,
        section_table=section_table,
        fallback_table=fallback_table,
        build_rag=build_rag,
        rag_index_path=effective_rag_index,
    )
    return {
        "syllabus_url": syllabus_url,
        "discovered_urls": len(urls),
        "download_report": download_report,
        "process_report": process_report,
        "rag_index_path": effective_rag_index if build_rag else None,
    }


def compute_file_hash(path: str, algorithm: str = "sha256") -> str:
    h = hashlib.new(algorithm)
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


def ocr_pdf(pdf_path: str, max_pages: Optional[int] = None) -> str:
    if pypdfium2 is None or pytesseract is None:
        raise RuntimeError("OCR fallback requires pypdfium2 and pytesseract")

    doc = pypdfium2.PdfDocument(pdf_path)
    pages = []
    for i, page in enumerate(doc):
        if max_pages is not None and i >= max_pages:
            break
        pil = page.render_topil(scale=2)
        text = pytesseract.image_to_string(pil)
        pages.append(text)
        page.close()
    return "\n\n".join(pages)


def extract_text_from_pdf(pdf_path: str) -> str:
    text = ""
    try:
        with pdfplumber.open(pdf_path) as pdf:
            pages = [page.extract_text() or "" for page in pdf.pages]
            text = "\n\n".join(pages).strip()
    except Exception:
        text = ""

    if not text:
        try:
            text = ocr_pdf(pdf_path)
        except Exception:
            text = ""

    return text


def parse_curriculum(raw_text: str) -> Dict[str, Any]:
    lines = _normalize_text_lines(raw_text)
    title = lines[0] if lines else ""

    grade_map: Dict[str, Dict[str, Any]] = {}
    current_grade = "general"
    grade_map[current_grade] = _empty_grade_bucket(current_grade)
    current_section: Optional[Dict[str, Any]] = None

    for line in lines[1:]:
        class_match = _CLASS_HEADING_RE.match(line) or _SYLLABUS_CLASS_HEADING_RE.match(line)
        if class_match:
            _append_section(grade_map[current_grade], current_section)
            current_section = None
            current_grade = (class_match.group(1) or class_match.group(2) or "").upper()
            grade_map.setdefault(current_grade, _empty_grade_bucket(current_grade))
            continue

        is_section_heading = bool(_SECTION_HEADING_RE.match(line)) or line.endswith(":")
        if is_section_heading:
            _append_section(grade_map[current_grade], current_section)
            current_section = {"heading": line.rstrip(":"), "content": []}
            continue

        if current_section is None:
            current_section = {"heading": "Introduction", "content": []}
        current_section["content"].append(line)

    _append_section(grade_map[current_grade], current_section)

    # If explicit class grades are present, move leading generic sections into the
    # first detected class to avoid saving mixed documents as grade 0 entries.
    specific_grades = [grade for grade in grade_map.keys() if _grade_to_int(grade) is not None]
    general_bucket = grade_map.get("general")
    if specific_grades and general_bucket and general_bucket.get("sections"):
        first_specific_grade = specific_grades[0]
        grade_map[first_specific_grade]["sections"] = (
            general_bucket["sections"] + grade_map[first_specific_grade].get("sections", [])
        )
        general_bucket["sections"] = []

    grades = [bucket for bucket in grade_map.values() if bucket.get("sections")]
    flat_sections: List[Dict[str, Any]] = []
    for grade_bucket in grades:
        grade_label = grade_bucket["grade"]
        for section in grade_bucket["sections"]:
            flat_sections.append(
                {
                    "grade": grade_label,
                    "heading": section["heading"],
                    "content": section["content"],
                }
            )

    return {
        "total_lines": len(lines),
        "title": title,
        "sections": flat_sections,
        "grades": grades,
    }


def _flatten_grade_sections(parsed: Dict[str, Any], document_id: str) -> List[Dict[str, Any]]:
    section_rows: List[Dict[str, Any]] = []
    grades = parsed.get("grades", [])

    for grade_bucket in grades:
        grade = grade_bucket.get("grade", "general")
        for index, section in enumerate(grade_bucket.get("sections", []), start=1):
            grade_as_int = _grade_to_int(grade)
            section_rows.append(
                {
                    "id": str(uuid.uuid4()),
                    "document_id": document_id,
                    "grade": grade,
                    "grade_number": grade_as_int,
                    "section_index": index,
                    "heading": section.get("heading", ""),
                    "content": section.get("content", []),
                }
            )
    return section_rows


def _build_curriculum_item_rows(parsed: Dict[str, Any], curriculum_group_id: str, source_id: str) -> List[Dict[str, Any]]:
    rows: List[Dict[str, Any]] = []
    title = str(parsed.get("title", "") or "Curriculum")
    subject = re.sub(r"\s*\(.*\)\s*$", "", title).strip() or "General"
    grades = parsed.get("grades", [])
    detected_numeric_grades = [
        grade_int for grade_int in (_grade_to_int(str(g.get("grade", "") or "")) for g in grades) if grade_int is not None
    ]
    inferred_default_grade = min(detected_numeric_grades) if detected_numeric_grades else None

    for grade_bucket in grades:
        grade_label = str(grade_bucket.get("grade", "") or "")
        grade_int = _grade_to_int(grade_label)
        if grade_int is None and inferred_default_grade is not None:
            grade_int = inferred_default_grade
        elif grade_int is None:
            grade_int = 0

        for section_index, section in enumerate(grade_bucket.get("sections", []), start=1):
            heading = str(section.get("heading", "") or "").strip() or "Untitled"
            content_lines = [str(line).strip() for line in section.get("content", []) if str(line).strip()]
            description = "\n".join(content_lines) if content_lines else None
            keywords = []
            for token in _tokenize(f"{heading} {subject} {' '.join(content_lines[:5])}"):
                if token not in keywords:
                    keywords.append(token)
                if len(keywords) >= 8:
                    break

            rows.append(
                {
                    "curriculum_group_id": curriculum_group_id,
                    "source_id": source_id,
                    "grade": grade_int,
                    "subject": subject,
                    "unit_title": heading,
                    "lesson_title": heading,
                    "description": description,
                    "item_type": "lesson",
                    "status": "active",
                    "grade_code": grade_label or None,
                    "grade_sort_order": grade_int or None,
                    "source_section": heading,
                    "source_reference": f"{grade_label}:{heading}" if grade_label else heading,
                    "learning_objectives": content_lines,
                    "keywords": keywords,
                    "meta": {
                        "grade_label": grade_label,
                        "line_count": len(content_lines),
                        "section_index": section_index,
                        "heading": heading,
                        "content_lines": content_lines,
                        "json_section": {
                            "grade": grade_label,
                            "heading": heading,
                            "content": content_lines,
                        },
                    },
                }
            )

    return rows


def _save_to_curriculum_schema(supabase: Any, result: CurriculumParseResult, curriculum_group_id: str) -> Dict[str, Any]:
    ui_payload = build_ui_curriculum_payload(result, include_raw_text=True)
    full_model = result.model_dump()
    source_name = Path(result.source).name
    source_row = {
        "curriculum_group_id": curriculum_group_id,
        "source_type": "web",
        "source_name": source_name,
        "source_url": result.source,
        # Dedicated top-level column — will be silently dropped by _insert_with_column_adaptation
        # if the column does not exist in the DB schema.
        "json_payload": full_model,
        "meta": {
            "json_payload": full_model,
            "ui_payload": ui_payload,
            "parsed": result.parsed,
            "raw_text": result.raw_text,
            "ai_summary": result.ai_summary,
            "raw_text_length": result.raw_text_length,
            "has_ai_summary": bool(result.ai_summary),
        },
    }
    existing_source = _find_existing_curriculum_source(supabase, curriculum_group_id, source_name, result.source)
    if existing_source:
        source_id = existing_source.get("source_id") or existing_source.get("id")
        if not source_id:
            raise RuntimeError("Existing curriculum source row was found but source_id was missing")
        source_response = _update_with_column_adaptation(
            supabase,
            "curriculum_sources",
            dict(source_row),
            "source_id",
            source_id,
        )
        _delete_curriculum_items_for_source(supabase, str(source_id))
        source_action = "updated"
    else:
        source_response = _insert_with_column_adaptation(supabase, "curriculum_sources", dict(source_row))
        source_rows = source_response.data or []
        if not source_rows:
            raise RuntimeError("Inserted curriculum source but no row was returned")

        source_id = source_rows[0].get("source_id") or source_rows[0].get("id")
        if not source_id:
            raise RuntimeError("Unable to determine source_id after source insert")
        source_action = "inserted"

    item_rows = _build_curriculum_item_rows(result.parsed or {}, curriculum_group_id, str(source_id))
    item_response: Optional[Dict[str, Any]] = None
    if item_rows:
        item_response = _upsert_curriculum_items(supabase, item_rows)

    return {
        "mode": "normalized_tables",
        "document_table": "curriculum_sources",
        "section_table": "curriculum_items",
        "source_id": str(source_id),
        "source_action": source_action,
        "sections_saved": len(item_rows),
        "document_response": source_response,
        "section_response": item_response,
    }


def save_curriculum_to_supabase(
    result: CurriculumParseResult,
    document_table: str = "curriculum_sources",
    section_table: str = "curriculum_items",
    fallback_table: str = "curriculum_sources",
) -> Dict[str, Any]:
    load_supabase_env_from_registry()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set")
    if create_client is None:
        raise RuntimeError("supabase package is not installed")

    supabase = create_client(url, key)
    parsed = result.model_dump()
    curriculum_group_id = resolve_curriculum_group_id(supabase)

    document_row = {
        "id": parsed["id"],
        "curriculum_group_id": curriculum_group_id,
        "source": parsed["source"],
        "raw_text_length": parsed["raw_text_length"],
        "title": parsed.get("parsed", {}).get("title", ""),
        "total_lines": parsed.get("parsed", {}).get("total_lines", 0),
        "raw_text": parsed["raw_text"],
        "ai_summary": parsed.get("ai_summary"),
        "parsed": parsed.get("parsed", {}),
    }

    section_rows = _flatten_grade_sections(parsed.get("parsed", {}), parsed["id"])
    for row in section_rows:
        if isinstance(row.get("grade"), str):
            numeric = _grade_to_int(row.get("grade", ""))
            if numeric is not None:
                row["grade"] = numeric

    try:
        if document_table == "curriculum_sources" and section_table == "curriculum_items":
            return _save_to_curriculum_schema(supabase, result, curriculum_group_id)

        doc_response = _insert_with_column_adaptation(supabase, document_table, document_row)
        section_response = None
        if section_rows:
            section_response = _insert_with_column_adaptation(supabase, section_table, section_rows)
        return {
            "mode": "normalized_tables",
            "document_table": document_table,
            "section_table": section_table,
            "sections_saved": len(section_rows),
            "document_response": doc_response,
            "section_response": section_response,
        }
    except Exception as exc:
        primary_error = str(exc)
        try:
            fallback_response = _insert_with_column_adaptation(supabase, fallback_table, parsed)
            return {
                "mode": "fallback_table",
                "fallback_table": fallback_table,
                "reason": primary_error,
                "fallback_response": fallback_response,
            }
        except Exception as fallback_exc:
            raise RuntimeError(
                f"Supabase save failed for normalized tables and fallback table. "
                f"primary_error={primary_error}; fallback_error={fallback_exc}"
            ) from fallback_exc


def process_pdf(pdf_path: str, use_ai: bool = False) -> CurriculumParseResult:
    load_supabase_env_from_registry()
    raw_text = extract_text_from_pdf(pdf_path)
    parsed = parse_curriculum(raw_text)

    ai_summary = None
    if use_ai and raw_text.strip():
        try:
            ai_summary = create_ai_summary(raw_text)
        except Exception as exc:
            ai_summary = f"AI summary failed: {exc}"

    return CurriculumParseResult(
        id=str(uuid.uuid4()),
        source=str(pdf_path),
        raw_text_length=len(raw_text),
        parsed=parsed,
        raw_text=raw_text,
        ai_summary=ai_summary,
    )


def discover_ncert_pdf_urls(syllabus_url: str = "https://ncert.nic.in/syllabus.php?ln=en") -> List[str]:
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Connection": "keep-alive",
        "Referer": "https://ncert.nic.in/",
    }

    pdf_links = set()
    last_error = None
    for attempt in range(1, 5):
        try:
            response = requests.get(syllabus_url, headers=headers, timeout=30)
            response.raise_for_status()
            soup = BeautifulSoup(response.text, "html.parser")
            for a in soup.find_all("a", href=True):
                href = a["href"]
                if href.lower().endswith(".pdf"):
                    if href.startswith("http"):
                        pdf_links.add(href)
                    else:
                        pdf_links.add("https://ncert.nic.in/" + href.lstrip("/"))
            break
        except Exception as exc:
            last_error = exc
            time.sleep(attempt * 2)
    else:
        raise RuntimeError(f"Failed to discover NCERT URLs: {last_error}")

    if not pdf_links:
        raise RuntimeError("No PDF links found on NCERT syllabus page; site may be blocking requests.")

    return sorted(pdf_links)


def fetch_ncert_pdfs(dest_dir: str, urls: List[str]) -> List[Dict[str, Any]]:
    Path(dest_dir).mkdir(parents=True, exist_ok=True)
    manifest_path = Path(dest_dir) / "manifest.json"
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    else:
        manifest = {}

    session = requests.Session()
    retries = requests.adapters.Retry(total=5, backoff_factor=1, status_forcelist=[429, 500, 502, 503, 504])
    adapter = requests.adapters.HTTPAdapter(max_retries=retries)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/122.0.0.0 Safari/537.36",
        "Accept": "application/pdf,application/octet-stream;q=0.9,*/*;q=0.8",
        "Accept-Language": "en-US,en;q=0.9",
        "Referer": "https://ncert.nic.in/",
        "Connection": "keep-alive",
    }

    results = []

    for url in urls:
        filename = os.path.basename(url.split("?")[0]) or f"{uuid.uuid4()}.pdf"
        dest_file = Path(dest_dir) / filename
        prev_hash = manifest.get(str(dest_file), {}).get("sha256")

        if dest_file.exists() and prev_hash:
            current_hash = compute_file_hash(str(dest_file))
            if current_hash == prev_hash:
                results.append({"url": url, "file": str(dest_file), "status": "skipped", "sha256": current_hash})
                continue

        error_msg = None
        for attempt in range(1, 5):
            try:
                response = session.get(url, stream=True, timeout=60, headers=headers)
                response.raise_for_status()
                if "application/pdf" not in response.headers.get("Content-Type", "").lower():
                    raise ValueError(f"URL did not return PDF: {url}, content-type={response.headers.get('Content-Type')}")

                with open(dest_file, "wb") as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if chunk:
                            f.write(chunk)

                file_hash = compute_file_hash(str(dest_file))
                manifest[str(dest_file)] = {
                    "url": url,
                    "sha256": file_hash,
                    "downloaded_at": time.time(),
                }
                results.append({"url": url, "file": str(dest_file), "status": "downloaded", "sha256": file_hash})
                error_msg = None
                break
            except Exception as exc:
                error_msg = str(exc)
                time.sleep(attempt * 2)

        if error_msg is not None:
            results.append({"url": url, "file": str(dest_file), "status": "error", "error": error_msg})

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)

    return results


def save_to_supabase(document: Dict[str, Any], table: str = "curriculum") -> Dict[str, Any]:
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key:
        raise RuntimeError("SUPABASE_URL and SUPABASE_KEY must be set")
    if create_client is None:
        raise RuntimeError("supabase package is not installed")

    supabase = create_client(url, key)
    response = supabase.table(table).insert(document).execute()
    return response


def _curriculum_record_exists_in_supabase(
    pdf_file: Path,
    document_table: str = "curriculum_sources",
    section_table: str = "curriculum_items",
    fallback_table: str = "curriculum_sources",
) -> bool:
    load_supabase_env_from_registry()
    url = os.getenv("SUPABASE_URL")
    key = os.getenv("SUPABASE_KEY")
    if not url or not key or create_client is None:
        return False

    try:
        supabase = create_client(url, key)

        if document_table == "curriculum_sources" and section_table == "curriculum_items":
            source_rows = (
                supabase.table("curriculum_sources")
                .select("source_id")
                .eq("source_name", pdf_file.name)
                .limit(20)
                .execute()
                .data
                or []
            )
            for source_row in source_rows:
                source_id = source_row.get("source_id") or source_row.get("id")
                if not source_id:
                    continue
                item_rows = (
                    supabase.table("curriculum_items")
                    .select("id")
                    .eq("source_id", source_id)
                    .limit(1)
                    .execute()
                    .data
                    or []
                )
                if item_rows:
                    return True
            return False

        for table_name, column, value in [
            (document_table, "source", str(pdf_file)),
            (document_table, "source_name", pdf_file.name),
            (fallback_table, "source", str(pdf_file)),
            (fallback_table, "source_name", pdf_file.name),
        ]:
            try:
                rows = (
                    supabase.table(table_name)
                    .select("*")
                    .eq(column, value)
                    .limit(1)
                    .execute()
                    .data
                    or []
                )
                if rows:
                    return True
            except Exception:
                continue
    except Exception:
        return False

    return False


def process_ncert_batch(
    pdf_dir: str,
    output_dir: str,
    use_ai: bool = False,
    save_supabase: bool = False,
    force_reprocess: bool = False,
    document_table: str = "curriculum_sources",
    section_table: str = "curriculum_items",
    fallback_table: str = "curriculum_sources",
    build_rag: bool = False,
    rag_index_path: Optional[str] = None,
) -> List[Dict[str, Any]]:
    Path(output_dir).mkdir(parents=True, exist_ok=True)
    manifest_path = Path(output_dir) / "processed_manifest.json"
    if manifest_path.exists():
        with open(manifest_path, "r", encoding="utf-8") as f:
            processed_manifest = json.load(f)
    else:
        processed_manifest = {}

    report = []
    for pdf_file in Path(pdf_dir).glob("*.pdf"):
        file_hash = compute_file_hash(str(pdf_file))
        existing = processed_manifest.get(str(pdf_file))
        if not force_reprocess and existing and existing.get("sha256") == file_hash:
            if not save_supabase:
                report.append({"file": str(pdf_file), "status": "already_processed"})
                continue

            if _curriculum_record_exists_in_supabase(
                pdf_file,
                document_table=document_table,
                section_table=section_table,
                fallback_table=fallback_table,
            ):
                report.append({"file": str(pdf_file), "status": "already_processed"})
                continue

        parsed = process_pdf(str(pdf_file), use_ai=use_ai)

        output_path = Path(output_dir) / (pdf_file.stem + ".json")
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(parsed.model_dump(), f, ensure_ascii=False, indent=2)

        processed_manifest[str(pdf_file)] = {
            "sha256": file_hash,
            "processed_at": time.time(),
            "output": str(output_path),
        }

        rag_result = None
        if build_rag:
            effective_rag_index = rag_index_path or str(Path(output_dir) / "rag_index.json")
            rag_result = update_rag_index(parsed, effective_rag_index)

        if save_supabase:
            try:
                supabase_result = save_curriculum_to_supabase(
                    parsed,
                    document_table=document_table,
                    section_table=section_table,
                    fallback_table=fallback_table,
                )
                report.append(
                    {
                        "file": str(pdf_file),
                        "status": "processed_supabase",
                        "reprocessed_from_manifest": bool(existing and existing.get("sha256") == file_hash),
                        "supabase_mode": supabase_result.get("mode"),
                        "sections_saved": supabase_result.get("sections_saved", 0),
                        "rag_chunks_saved": (rag_result or {}).get("chunks_saved", 0),
                    }
                )
            except Exception as e:
                report.append({"file": str(pdf_file), "status": "processed_no_supabase", "error": str(e)})
                continue
        else:
            report.append(
                {
                    "file": str(pdf_file),
                    "status": "processed",
                    "rag_chunks_saved": (rag_result or {}).get("chunks_saved", 0),
                }
            )

    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(processed_manifest, f, indent=2)

    return report
