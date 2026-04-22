"""
Patient report extraction and graph helpers.

This module keeps uploaded PDF report processing out of the attachment registry
by storing a sidecar JSON next to each uploaded file.
"""

from __future__ import annotations

import json
import os
import re
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Tuple

import requests

try:
    from pypdf import PdfReader
except ImportError:  # pragma: no cover - optional runtime dependency
    PdfReader = None

from src.ssl_bootstrap import get_ssl_cert_path
from src.vision_tool import OPENROUTER_API_KEY, OPENROUTER_URL, VISION_MODELS, encode_image

try:
    import fitz  # type: ignore
except ImportError:  # pragma: no cover - optional runtime dependency
    fitz = None


PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
UPLOADS_DIR = os.path.join(PROJECT_ROOT, "uploads")
STORAGE_DIR = os.path.join(PROJECT_ROOT, "storage")
PATIENT_FILES_REGISTRY = os.path.join(STORAGE_DIR, "patient_files.json")
REPORT_SIDECAR_SUFFIX = ".report.json"

REPORT_DOCUMENT_VISION_PROMPT = """You are reading a scanned clinical report page.
Transcribe the visible report text faithfully.

Rules:
- Preserve clinically important wording, numbers, units, dates, and medication names.
- If a section heading is visible, keep it.
- If a vital sign is visible, preserve its value and unit exactly.
- Do not infer or summarize beyond the visible page.
- Output plain text only. No markdown fences.
"""

SECTION_ALIASES = {
    "summary": "summary",
    "history": "history",
    "findings": "findings",
    "interpretation": "findings",
    "result": "findings",
    "results": "findings",
    "impression": "impression",
    "assessment": "impression",
    "conclusion": "impression",
    "comment": "summary",
    "comments": "summary",
    "note": "recommendations",
    "diagnosis": "diagnoses",
    "diagnoses": "diagnoses",
    "medication": "medications",
    "medications": "medications",
    "recommendation": "recommendations",
    "recommendations": "recommendations",
    "plan": "recommendations",
    "follow up": "recommendations",
    "follow-up": "recommendations",
}

REPORT_BOILERPLATE_PREFIXES = (
    "name :",
    "page ",
    "classification:",
    "lab no",
    "ref by",
    "collected",
    "a/c status",
    "collected at",
    "age",
    "gender",
    "reported",
    "report status",
    "processed at",
    "test report",
    "test name",
    "results units",
    "bio. ref.",
    "interval",
    "final",
    "male",
    "female",
    "important instructions",
    "end of report",
    "technical director",
    "national reference lab",
    "tel:",
    "fax:",
    "e-mail:",
)

DATE_PATTERNS = (
    r"\b\d{4}-\d{2}-\d{2}\b",
    r"\b\d{1,2}/\d{1,2}/\d{2,4}\b",
    r"\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|sept|oct|nov|dec)[a-z]* \d{1,2}, \d{4}\b",
)


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def attachment_path_from_url(url: Optional[str]) -> Optional[str]:
    prefix = "/uploads/"
    if not url or not str(url).startswith(prefix):
        return None
    relative_path = str(url)[len(prefix):]
    return os.path.join(UPLOADS_DIR, relative_path)


def attachment_sidecar_path(file_path: str) -> str:
    return f"{file_path}{REPORT_SIDECAR_SUFFIX}"


def _load_json(path: str) -> Optional[dict]:
    try:
        with open(path, "r") as handle:
            return json.load(handle)
    except (OSError, json.JSONDecodeError):
        return None


def _write_json(path: str, payload: dict):
    with open(path, "w") as handle:
        json.dump(payload, handle, indent=2)


def load_attachment_sidecar(file_path: Optional[str]) -> Optional[dict]:
    if not file_path:
        return None
    return _load_json(attachment_sidecar_path(file_path))


def _normalize_space(value: str) -> str:
    return re.sub(r"\s+", " ", str(value or "")).strip()


def _summary_preview(value: str, limit: int = 160) -> str:
    text = _normalize_space(value)
    if len(text) <= limit:
        return text
    return text[:limit].rsplit(" ", 1)[0] + "..."


def _parse_datetime(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None

    text = str(value).strip()
    if not text:
        return None

    normalized = text.replace("Z", "+00:00")
    try:
        return datetime.fromisoformat(normalized)
    except ValueError:
        pass

    for fmt in (
        "%Y-%m-%d",
        "%Y-%m-%d %H:%M:%S",
        "%Y-%m-%d %H:%M",
        "%m/%d/%Y",
        "%m/%d/%y",
        "%m/%d/%Y %H:%M",
        "%b %d, %Y",
        "%B %d, %Y",
    ):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue

    return None


def _read_attachment_registry() -> List[dict]:
    data = _load_json(PATIENT_FILES_REGISTRY)
    return data if isinstance(data, list) else []


def patient_attachment_records(patient_id: str) -> List[dict]:
    records = []
    for record in _read_attachment_registry():
        if str(record.get("patient_id")) == str(patient_id):
            records.append(record)
    records.sort(key=lambda item: item.get("uploaded_at") or "", reverse=True)
    return records


def _extract_pdf_text(file_path: str) -> str:
    if PdfReader is None:
        raise RuntimeError("pypdf is not installed for local PDF text extraction.")

    reader = PdfReader(file_path)
    pages: List[str] = []
    for page in reader.pages:
        try:
            pages.append(page.extract_text() or "")
        except Exception:
            continue
    return "\n".join(part.strip() for part in pages if part and part.strip())


def _text_is_thin(text: str) -> bool:
    stripped = _normalize_space(text)
    if len(stripped) < 180:
        return True
    return len(stripped.split()) < 40


def _render_pdf_pages(file_path: str, max_pages: int = 2) -> List[str]:
    if fitz is None:
        raise RuntimeError("PyMuPDF is not installed for scanned PDF rendering.")

    image_paths: List[str] = []
    document = fitz.open(file_path)
    try:
        temp_dir = tempfile.mkdtemp(prefix="report-pages-")
        for index in range(min(len(document), max_pages)):
            page = document.load_page(index)
            pixmap = page.get_pixmap(matrix=fitz.Matrix(2, 2), alpha=False)
            output_path = os.path.join(temp_dir, f"page-{index + 1}.png")
            pixmap.save(output_path)
            image_paths.append(output_path)
    finally:
        document.close()

    return image_paths


def _transcribe_report_page_with_vision(image_path: str) -> str:
    if not OPENROUTER_API_KEY:
        raise RuntimeError("OPENROUTER_API_KEY is not configured for report OCR fallback.")

    base64_image = encode_image(image_path)
    ext = os.path.splitext(image_path)[1].lower()
    mime_type = "image/jpeg" if ext in (".jpg", ".jpeg") else "image/png"

    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json",
        "HTTP-Referer": "https://trustmed-ai.local",
        "X-Title": "TrustMed AI Report OCR",
    }

    errors: List[str] = []
    for model_id in VISION_MODELS:
        payload = {
            "model": model_id,
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": REPORT_DOCUMENT_VISION_PROMPT},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:{mime_type};base64,{base64_image}"},
                        },
                    ],
                }
            ],
            "temperature": 0.1,
            "max_tokens": 1200,
        }

        response = requests.post(
            OPENROUTER_URL,
            headers=headers,
            json=payload,
            timeout=90,
            verify=get_ssl_cert_path() or True,
        )

        if response.status_code == 404:
            errors.append(f"{model_id}: not found")
            continue
        if response.status_code != 200:
            errors.append(f"{model_id}: {response.status_code}")
            continue

        data = response.json()
        content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
        if content:
            return str(content).strip()
        errors.append(f"{model_id}: empty response")

    raise RuntimeError("Vision fallback failed: " + "; ".join(errors))


def _transcribe_pdf_with_vision(file_path: str, max_pages: int = 2) -> str:
    pages = _render_pdf_pages(file_path, max_pages=max_pages)
    transcribed: List[str] = []
    for page_path in pages:
        transcribed.append(_transcribe_report_page_with_vision(page_path))
    return "\n\n".join(part.strip() for part in transcribed if part and part.strip())


def _split_sentences(text: str) -> List[str]:
    sentences = re.split(r"(?<=[.!?])\s+", _normalize_space(text))
    return [item.strip(" -\u2022") for item in sentences if item.strip(" -\u2022")]


def _extract_sections(text: str) -> Dict[str, List[str]]:
    sections: Dict[str, List[str]] = {"body": []}
    current = "body"

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            continue

        inline_match = re.match(r"^([A-Za-z][A-Za-z /-]{1,30})\s*:\s*(.+)$", line)
        if inline_match:
            heading = inline_match.group(1).strip().lower()
            canonical = SECTION_ALIASES.get(heading)
            if canonical:
                sections.setdefault(canonical, []).append(inline_match.group(2).strip())
                current = canonical
                continue

        heading = line.strip(":").strip().lower()
        canonical = SECTION_ALIASES.get(heading)
        if canonical and len(line.split()) <= 4:
            current = canonical
            sections.setdefault(current, [])
            continue

        sections.setdefault(current, []).append(line)

    return sections


def _section_text(sections: Dict[str, List[str]], key: str) -> str:
    return "\n".join(sections.get(key, [])).strip()


def _candidate_items(block: str) -> List[str]:
    items: List[str] = []
    for part in re.split(r"\n|;|(?<=[.!?])\s+", str(block or "")):
        cleaned = _normalize_space(part).strip(" -\u2022")
        if len(cleaned) < 4:
            continue
        if cleaned.lower() in {"none", "n/a", "not applicable"}:
            continue
        lowered = cleaned.lower()
        if lowered.startswith(REPORT_BOILERPLATE_PREFIXES):
            continue
        if cleaned.startswith("|") or cleaned.startswith("-") or re.fullmatch(r"[-|.=]{4,}", cleaned):
            continue
        items.append(cleaned)
    return items


def _extract_lab_result_items(text: str) -> List[str]:
    normalized = _normalize_space(text)
    matches = re.findall(
        r"\b([A-Za-z][A-Za-z .&/-]{2,60}?Ig[GM])\s+([<>]?\d+(?:\.\d+)?)\b",
        normalized,
        flags=re.I,
    )
    results = []
    for label, value in matches:
        cleaned_label = _normalize_space(label).replace("M.pneumoniae", "M. pneumoniae")
        results.append(f"{cleaned_label}: {value}")
    return _dedupe_preserve(results)


def _dedupe_preserve(items: Iterable[str]) -> List[str]:
    deduped: List[str] = []
    seen = set()
    for item in items:
        cleaned = _normalize_space(item)
        if not cleaned:
            continue
        key = cleaned.lower()
        if key in seen:
            continue
        seen.add(key)
        deduped.append(cleaned)
    return deduped


def _extract_report_date(text: str, uploaded_at: Optional[str]) -> Optional[str]:
    lowered = text.lower()
    for label in ("report date", "exam date", "date", "service date"):
        label_match = re.search(label + r"\s*[:\-]?\s*(" + "|".join(DATE_PATTERNS) + r")", lowered, re.I)
        if label_match:
            parsed = _parse_datetime(label_match.group(1))
            if parsed:
                return parsed.isoformat()

    generic_match = re.search("|".join(DATE_PATTERNS), text, re.I)
    if generic_match:
        parsed = _parse_datetime(generic_match.group(0))
        if parsed:
            return parsed.isoformat()

    parsed_uploaded = _parse_datetime(uploaded_at)
    return parsed_uploaded.isoformat() if parsed_uploaded else uploaded_at


def _extract_vitals(text: str, recorded_at: Optional[str]) -> Dict[str, Any]:
    vitals: Dict[str, Any] = {}

    blood_pressure = re.search(
        r"(?:blood pressure|bp)\s*[:=]?\s*(\d{2,3})\s*[/\-]\s*(\d{2,3})",
        text,
        re.I,
    )
    if blood_pressure:
        vitals["systolic_bp"] = int(blood_pressure.group(1))
        vitals["diastolic_bp"] = int(blood_pressure.group(2))

    heart_rate = re.search(r"(?:heart rate|hr|pulse)\s*[:=]?\s*(\d{2,3})", text, re.I)
    if heart_rate:
        vitals["heart_rate"] = int(heart_rate.group(1))

    respiratory_rate = re.search(r"(?:resp(?:iratory)?(?: rate)?|rr)\s*[:=]?\s*(\d{1,2})", text, re.I)
    if respiratory_rate:
        vitals["respiratory_rate"] = int(respiratory_rate.group(1))

    oxygen = re.search(r"(?:spo2|o2 sat(?:uration)?|oxygen saturation)\s*[:=]?\s*(\d{2,3})\s*%?", text, re.I)
    if oxygen:
        vitals["o2_saturation"] = int(oxygen.group(1))

    temperature = re.search(r"(?:temp(?:erature)?)\s*[:=]?\s*(\d{2,3}(?:\.\d+)?)\s*°?\s*([FC])?", text, re.I)
    if temperature:
        numeric = float(temperature.group(1))
        unit = (temperature.group(2) or "F").upper()
        if unit == "C":
            numeric = (numeric * 9 / 5) + 32
        vitals["temperature"] = round(numeric, 1)

    if vitals:
        vitals["recorded_at"] = recorded_at

    return vitals


def _extract_medications(text: str, sections: Dict[str, List[str]]) -> List[str]:
    section_items = _candidate_items(_section_text(sections, "medications"))
    dosage_hits = re.findall(
        r"\b([A-Z][A-Za-z0-9/-]+(?: [A-Z][A-Za-z0-9/-]+){0,2}\s+\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|mL|units?))\b",
        text,
    )
    return _dedupe_preserve(section_items + list(dosage_hits))


def _extract_structured_report(text: str, title: str, uploaded_at: Optional[str]) -> dict:
    sections = _extract_sections(text)
    report_date = _extract_report_date(text, uploaded_at)
    lab_results = _extract_lab_result_items(text)
    findings = _dedupe_preserve(
        lab_results +
        _candidate_items(_section_text(sections, "findings")) +
        _candidate_items(_section_text(sections, "summary")) +
        _candidate_items(_section_text(sections, "body"))
    )[:8]
    impression_items = _dedupe_preserve(
        _candidate_items(_section_text(sections, "impression")) +
        _candidate_items(_section_text(sections, "summary"))
    )[:4]
    diagnoses = _dedupe_preserve(
        _candidate_items(_section_text(sections, "diagnoses")) + impression_items[:3]
    )[:6]
    recommendations = _dedupe_preserve(
        _candidate_items(_section_text(sections, "recommendations"))
    )[:6]
    medications = _extract_medications(text, sections)[:8]
    vitals = _extract_vitals(text, report_date or uploaded_at)

    summary_source = impression_items or findings or _split_sentences(text)
    summary = " ".join(summary_source[:2]).strip()
    if not summary:
        summary = f"Uploaded report: {title}".strip()

    impression = " ".join(impression_items[:2]).strip()
    raw_text_excerpt = text[:1500].strip()

    return {
        "report_date": report_date,
        "summary": summary,
        "summary_preview": _summary_preview(summary or raw_text_excerpt),
        "findings": findings,
        "impression": impression,
        "diagnoses": diagnoses,
        "medications": medications,
        "vitals": vitals,
        "recommendations": recommendations,
        "raw_text_excerpt": raw_text_excerpt,
    }


def process_attachment_report(record: dict, force: bool = False) -> dict:
    file_path = attachment_path_from_url(record.get("url"))
    if not file_path:
        raise ValueError("Attachment URL does not map to a local file path.")

    sidecar_path = attachment_sidecar_path(file_path)
    if not force and os.path.exists(sidecar_path):
        existing = _load_json(sidecar_path)
        if isinstance(existing, dict):
            return existing

    payload = {
        "attachment_id": record.get("id"),
        "patient_id": str(record.get("patient_id") or ""),
        "title": record.get("title") or record.get("original_filename") or "Patient report",
        "original_filename": record.get("original_filename"),
        "uploaded_at": record.get("uploaded_at"),
        "processing_status": "failed",
        "processed_at": _utc_now_iso(),
        "summary": "",
        "summary_preview": "",
        "findings": [],
        "impression": "",
        "diagnoses": [],
        "medications": [],
        "vitals": {},
        "recommendations": [],
        "raw_text_excerpt": "",
        "report_date": record.get("uploaded_at"),
        "content_source": None,
        "extraction_error": None,
    }

    try:
        try:
            extracted_text = _extract_pdf_text(file_path)
        except Exception as exc:
            extracted_text = ""
            payload["extraction_error"] = str(exc)
        used_fallback = False

        if _text_is_thin(extracted_text):
            try:
                fallback_text = _transcribe_pdf_with_vision(file_path)
            except Exception as exc:
                fallback_text = ""
                payload["extraction_error"] = str(exc)
            if fallback_text:
                extracted_text = "\n\n".join(part for part in (extracted_text, fallback_text) if part.strip())
                used_fallback = True

        if not extracted_text.strip():
            raise ValueError("No extractable report text found.")

        payload.update(
            _extract_structured_report(
                extracted_text,
                title=payload["title"],
                uploaded_at=payload["uploaded_at"],
            )
        )
        payload["processing_status"] = "completed_with_fallback" if used_fallback else "completed"
        payload["content_source"] = "vision_fallback" if used_fallback else "local_text"
        payload["extraction_error"] = None
    except Exception as exc:
        payload["extraction_error"] = str(exc)
        if not payload["summary_preview"]:
            payload["summary_preview"] = _summary_preview(str(exc))

    _write_json(sidecar_path, payload)
    return payload


def _merge_attachment_report(record: dict, sidecar: Optional[dict]) -> dict:
    merged = dict(record)
    if not sidecar:
        return merged
    for key in (
        "report_date",
        "summary",
        "summary_preview",
        "findings",
        "impression",
        "diagnoses",
        "medications",
        "vitals",
        "recommendations",
        "raw_text_excerpt",
        "processed_at",
        "processing_status",
        "extraction_error",
        "content_source",
    ):
        merged[key] = sidecar.get(key)
    return merged


def load_patient_reports(patient_id: str, ensure_processed: bool = True) -> List[dict]:
    reports: List[dict] = []
    for record in patient_attachment_records(patient_id):
        if str(record.get("file_kind")) != "pdf":
            continue

        file_path = attachment_path_from_url(record.get("url"))
        if not file_path or not os.path.exists(file_path):
            continue

        sidecar = load_attachment_sidecar(file_path)
        if ensure_processed and sidecar is None:
            sidecar = process_attachment_report(record)

        reports.append(_merge_attachment_report(record, sidecar))

    reports.sort(
        key=lambda item: _parse_datetime(item.get("report_date") or item.get("uploaded_at")) or datetime.min,
        reverse=True,
    )
    return reports


def _format_report_vitals(vitals: dict) -> str:
    parts: List[str] = []
    if vitals.get("temperature") is not None:
        parts.append(f"Temp {vitals['temperature']} F")
    if vitals.get("heart_rate") is not None:
        parts.append(f"HR {round(vitals['heart_rate'])} bpm")
    if vitals.get("respiratory_rate") is not None:
        parts.append(f"RR {round(vitals['respiratory_rate'])}/min")
    if vitals.get("o2_saturation") is not None:
        parts.append(f"SpO2 {round(vitals['o2_saturation'])}%")
    if vitals.get("systolic_bp") is not None:
        diastolic = vitals.get("diastolic_bp")
        if diastolic is not None:
            parts.append(f"BP {round(vitals['systolic_bp'])}/{round(diastolic)}")
        else:
            parts.append(f"BP {round(vitals['systolic_bp'])}")
    return ", ".join(parts)


def build_patient_report_digest(patient_id: str, max_reports: int = 3) -> str:
    reports = load_patient_reports(patient_id)
    if not reports:
        return ""

    lines = ["Uploaded report context (most recent first):"]
    for report in reports[:max_reports]:
        title = report.get("title") or report.get("original_filename") or "Report"
        report_date = report.get("report_date") or report.get("uploaded_at") or "unknown date"
        summary = report.get("summary") or report.get("summary_preview") or "No report summary extracted."
        lines.append(f"- {title} ({report_date})")
        lines.append(f"  Summary: {summary}")

        vitals_text = _format_report_vitals(report.get("vitals") or {})
        if vitals_text:
            lines.append(f"  Report-derived vitals: {vitals_text}")

        findings = report.get("findings") or []
        if findings:
            lines.append("  Findings:")
            for finding in findings[:4]:
                lines.append(f"  - {finding}")

        diagnoses = report.get("diagnoses") or []
        if diagnoses:
            lines.append("  Diagnoses:")
            for diagnosis in diagnoses[:4]:
                lines.append(f"  - {diagnosis}")

        medications = report.get("medications") or []
        if medications:
            lines.append("  Medications:")
            for medication in medications[:4]:
                lines.append(f"  - {medication}")

    return "\n".join(lines)


def enrich_patient_data_with_reports(patient_data: dict) -> dict:
    if not patient_data or not patient_data.get("patient_id"):
        return patient_data

    patient_id = str(patient_data["patient_id"])
    reports = load_patient_reports(patient_id)

    enriched = dict(patient_data)

    chart_history = [dict(item) for item in (patient_data.get("vitals_history") or [])]
    combined_history: List[dict] = []
    for index, row in enumerate(chart_history):
        next_row = dict(row)
        next_row.setdefault("source", "chart")
        next_row["sort_order"] = index
        combined_history.append(next_row)

    report_vitals_rows: List[dict] = []
    for offset, report in enumerate(reversed(reports)):
        vitals = dict(report.get("vitals") or {})
        if not vitals:
            continue
        vitals["source"] = "report"
        vitals["attachment_id"] = report.get("id")
        vitals["report_title"] = report.get("title")
        vitals["report_date"] = report.get("report_date")
        vitals["processing_status"] = report.get("processing_status")
        vitals["sort_order"] = len(combined_history) + len(report_vitals_rows) + offset
        report_vitals_rows.append(vitals)

    combined_history.extend(report_vitals_rows)
    if combined_history:
        combined_history = sorted(combined_history, key=lambda item: item.get("sort_order", 0))
        enriched["vitals_history"] = combined_history
        enriched["vitals"] = dict(combined_history[-1])
    else:
        enriched["vitals_history"] = []
        enriched["vitals"] = None

    enriched["report_summaries"] = [
        {
            "attachment_id": report.get("id"),
            "title": report.get("title"),
            "report_date": report.get("report_date"),
            "summary": report.get("summary"),
            "summary_preview": report.get("summary_preview"),
            "processing_status": report.get("processing_status"),
            "uploaded_at": report.get("uploaded_at"),
            "extraction_error": report.get("extraction_error"),
        }
        for report in reports
    ]
    enriched["report_findings"] = _dedupe_preserve(
        finding
        for report in reports
        for finding in (report.get("findings") or [])
    )[:12]
    enriched["report_last_updated"] = (
        reports[0].get("processed_at")
        if reports
        else None
    )
    enriched["report_digest"] = build_patient_report_digest(patient_id)

    return enriched
