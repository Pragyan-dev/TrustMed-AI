"""
TrustMed AI - FastAPI Backend
Modern REST API wrapping the TrustMed Brain orchestrator.
Persistent chat history + multi-session support.
"""

import os
import sys
import json
import ast
# Forced reload to pick up src changes
import asyncio
import uuid
import time
import re
import mimetypes
import shutil
from typing import Optional, List, Dict
from pathlib import Path
from datetime import datetime, timezone
from threading import Lock
from fastapi import FastAPI, UploadFile, File, Form, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.trustmed_brain import (
    ask_trustmed,
    ask_trustmed_streaming,
    ask_trustmed_direct,
    generate_soap_note,
    get_patient_context,
)
import traceback
from src.vision_agent import get_vision_cache_stats, clear_vision_cache
from src.graph_visualizer import get_graph_json
from src.subfigure_detector import detect_compound_figure, split_compound_figure
from src.patient_context_tool import get_patient_data_json

app = FastAPI(
    title="TrustMed AI API",
    description="Clinical Decision Support API",
    version="2.0.0"
)

# CORS for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# =============================================================================
# Persistent Chat History
# =============================================================================

HISTORY_DIR = os.path.join(PROJECT_ROOT, "chat_history")
UPLOADS_DIR = os.path.join(PROJECT_ROOT, "uploads")
STORAGE_DIR = os.path.join(PROJECT_ROOT, "storage")
PATIENT_FILES_DIR = os.path.join(UPLOADS_DIR, "patient-files")
PATIENT_FILES_REGISTRY = os.path.join(STORAGE_DIR, "patient_files.json")
ATTACHMENT_REGISTRY_LOCK = Lock()
ATTACHMENT_PUBLIC_FIELDS = (
    "id",
    "patient_id",
    "title",
    "original_filename",
    "mime_type",
    "file_kind",
    "uploaded_by",
    "uploaded_at",
    "url",
)


def _ensure_dirs():
    """Create storage directories if they don't exist."""
    os.makedirs(HISTORY_DIR, exist_ok=True)
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    os.makedirs(STORAGE_DIR, exist_ok=True)
    os.makedirs(PATIENT_FILES_DIR, exist_ok=True)
    if not os.path.exists(PATIENT_FILES_REGISTRY):
        with open(PATIENT_FILES_REGISTRY, "w") as f:
            json.dump([], f)

# Serve uploaded images so they're accessible by URL in session history
_ensure_dirs()
app.mount("/uploads", StaticFiles(directory=UPLOADS_DIR), name="uploads")


def _uploads_url(abs_path: str) -> Optional[str]:
    if not abs_path:
        return None

    try:
        relative_path = Path(abs_path).resolve().relative_to(Path(UPLOADS_DIR).resolve())
    except ValueError:
        return None

    return f"/uploads/{str(relative_path).replace(os.sep, '/')}"


def _image_url(abs_path: str) -> Optional[str]:
    """Convert an absolute upload path to a serveable /uploads/... URL."""
    candidate = _uploads_url(abs_path)
    if candidate and os.path.exists(abs_path):
        return candidate
    return None


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _sanitize_path_segment(value: str, fallback: str) -> str:
    cleaned = re.sub(r"[^A-Za-z0-9._-]+", "-", str(value or "")).strip("-.")
    return cleaned or fallback


def _patient_attachment_dir(patient_id: str) -> str:
    safe_patient_id = _sanitize_path_segment(patient_id, "unknown-patient")
    attachment_dir = os.path.join(PATIENT_FILES_DIR, safe_patient_id)
    os.makedirs(attachment_dir, exist_ok=True)
    return attachment_dir


def _attachment_path_from_url(url: str) -> Optional[str]:
    prefix = "/uploads/"
    if not url or not url.startswith(prefix):
        return None
    relative_path = url[len(prefix):]
    return os.path.join(UPLOADS_DIR, relative_path)


def _normalize_patient_upload_mime_type(upload: UploadFile) -> Optional[str]:
    content_type = (upload.content_type or "").strip().lower()
    guessed_type, _ = mimetypes.guess_type(upload.filename or "")
    candidate = content_type or guessed_type or ""

    if candidate.startswith("image/"):
        return candidate
    if candidate == "application/pdf":
        return candidate
    return None


def _normalize_existing_file_mime_type(path: str) -> Optional[str]:
    guessed_type, _ = mimetypes.guess_type(path)
    candidate = (guessed_type or "").lower()

    if candidate.startswith("image/"):
        return candidate
    if candidate == "application/pdf":
        return candidate
    return None


def _derive_attachment_kind(mime_type: str) -> Optional[str]:
    if mime_type.startswith("image/"):
        return "image"
    if mime_type == "application/pdf":
        return "pdf"
    return None


def _default_attachment_title(filename: str, fallback: str) -> str:
    stem = os.path.splitext(os.path.basename(filename or ""))[0]
    readable = re.sub(r"[_-]+", " ", stem).strip()
    return readable or fallback


def _make_attachment_record(
    patient_id: str,
    stored_path: str,
    original_filename: str,
    mime_type: str,
    uploaded_by: str,
    title: Optional[str] = None,
) -> dict:
    file_kind = _derive_attachment_kind(mime_type)
    safe_filename = _sanitize_path_segment(original_filename, f"{file_kind or 'file'}")
    return {
        "id": uuid.uuid4().hex[:16],
        "patient_id": str(patient_id),
        "title": _default_attachment_title(title or safe_filename, "Patient report"),
        "original_filename": safe_filename,
        "mime_type": mime_type,
        "file_kind": file_kind,
        "uploaded_by": uploaded_by,
        "uploaded_at": _utc_now_iso(),
        "url": _uploads_url(stored_path),
    }


def _serialize_attachment(record: dict) -> dict:
    return {
        field: record.get(field)
        for field in ATTACHMENT_PUBLIC_FIELDS
    }


def _load_patient_attachment_registry() -> List[dict]:
    _ensure_dirs()
    with ATTACHMENT_REGISTRY_LOCK:
        try:
            with open(PATIENT_FILES_REGISTRY, "r") as f:
                data = json.load(f)
        except (json.JSONDecodeError, OSError):
            return []

    return data if isinstance(data, list) else []


def _append_patient_attachment(record: dict):
    _ensure_dirs()
    with ATTACHMENT_REGISTRY_LOCK:
        try:
            with open(PATIENT_FILES_REGISTRY, "r") as f:
                data = json.load(f)
            if not isinstance(data, list):
                data = []
        except (json.JSONDecodeError, OSError):
            data = []

        data.append(record)

        with open(PATIENT_FILES_REGISTRY, "w") as f:
            json.dump(data, f, indent=2)


def _list_patient_attachments(patient_id: str) -> List[dict]:
    attachments = []
    for record in _load_patient_attachment_registry():
        if str(record.get("patient_id")) != str(patient_id):
            continue

        attachment_path = _attachment_path_from_url(record.get("url"))
        if attachment_path and not os.path.exists(attachment_path):
            continue

        attachments.append(_serialize_attachment(record))

    attachments.sort(key=lambda item: item.get("uploaded_at") or "", reverse=True)
    return attachments


def _assert_path_in_uploads(abs_path: str):
    uploads_root = Path(UPLOADS_DIR).resolve()
    try:
        Path(abs_path).resolve().relative_to(uploads_root)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail="Clinician upload path must be inside the uploads directory.") from exc


def _session_path(session_id: str) -> str:
    """Get the JSON file path for a session."""
    safe_id = session_id.replace("/", "_").replace("\\", "_")
    return os.path.join(HISTORY_DIR, f"{safe_id}.json")


def _load_session(session_id: str) -> dict:
    """Load a session from disk. Returns default if not found."""
    path = _session_path(session_id)
    if os.path.exists(path):
        with open(path, "r") as f:
            return json.load(f)
    return {
        "id": session_id,
        "title": "New chat",
        "created_at": time.time(),
        "updated_at": time.time(),
        "messages": []
    }


def _save_session(session_id: str, data: dict):
    """Save a session to disk."""
    _ensure_dirs()
    data["updated_at"] = time.time()
    path = _session_path(session_id)
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


def _delete_session(session_id: str):
    """Delete a session file from disk."""
    path = _session_path(session_id)
    if os.path.exists(path):
        os.remove(path)


def _list_all_sessions() -> List[dict]:
    """List all saved sessions, sorted by most recent first."""
    _ensure_dirs()
    sessions = []
    for filename in os.listdir(HISTORY_DIR):
        if filename.endswith(".json"):
            filepath = os.path.join(HISTORY_DIR, filename)
            try:
                with open(filepath, "r") as f:
                    data = json.load(f)
                sessions.append({
                    "id": data.get("id", filename.replace(".json", "")),
                    "title": data.get("title", "Untitled"),
                    "message_count": len(data.get("messages", [])),
                    "updated_at": data.get("updated_at", 0),
                    "created_at": data.get("created_at", 0),
                    "source": data.get("source", "clinician"),
                })
            except (json.JSONDecodeError, IOError):
                continue
    # Most recent first
    sessions.sort(key=lambda s: s["updated_at"], reverse=True)
    return sessions


def _auto_title(message: str) -> str:
    """Generate a short title from the first user message."""
    title = message.strip()
    # Remove image attachment tags
    if "[ATTACHMENT:" in title:
        import re
        title = re.sub(r'\s*\[ATTACHMENT:.*?\]', '', title).strip()
    if not title:
        return "Image analysis"
    # Truncate to ~50 chars at a word boundary
    if len(title) > 50:
        title = title[:50].rsplit(" ", 1)[0] + "..."
    return title


PATIENT_ASSISTANT_SCOPE_REPLY = (
    "I can only help with your health record, medications, vitals, imaging, "
    "lab results, and care plan. Ask me about your visit or chart data."
)

_PATIENT_ALWAYS_BLOCK_PATTERNS = [
    re.compile(r"\b(write|generate|create|make|build)\s+(a\s+)?(python|javascript|java|c\+\+|c#|html|css|sql|code|program|script)\b", re.I),
    re.compile(r"\b(python|javascript|typescript|java|c\+\+|rust|golang|node\.?js|react)\b", re.I),
    re.compile(r"\b(prime numbers?|leetcode|binary tree|algorithm|sort an array)\b", re.I),
]

_PATIENT_OFF_TOPIC_PATTERNS = [
    re.compile(r"\b(recipe|weather|movie|song|poem|essay|resume|cover letter|crypto|stock market)\b", re.I),
    re.compile(r"\btranslate\b", re.I),
]

_PATIENT_MEDICAL_SCOPE_PATTERNS = [
    re.compile(
        r"\b(health|visit|record|chart|doctor|care team|medical|diagnosis|diagnoses|condition|symptom|symptoms|"
        r"medication|medications|medicine|drug|drugs|dose|side effect|interaction|allergy|vitals?|blood pressure|"
        r"heart rate|pulse|oxygen|spo2|temperature|fever|breathing|respiratory|lab|labs|test result|results|"
        r"imaging|x-ray|ct|mri|scan|ultrasound|report|care plan|follow-up|treatment|infection|pain|cough|"
        r"glucose|cholesterol)\b",
        re.I,
    )
]


def _get_assistant_mode(request, session: dict) -> str:
    return (request.assistant_mode or session.get("source") or "clinician").lower()


def _is_off_topic_patient_question(message: str) -> bool:
    normalized = (message or "").strip()
    if not normalized:
        return False
    if any(pattern.search(normalized) for pattern in _PATIENT_ALWAYS_BLOCK_PATTERNS):
        return True
    if any(pattern.search(normalized) for pattern in _PATIENT_MEDICAL_SCOPE_PATTERNS):
        return False
    return any(pattern.search(normalized) for pattern in _PATIENT_OFF_TOPIC_PATTERNS)


def _build_patient_portal_context(patient_data: dict, patient_id: Optional[str]) -> str:
    if not patient_data:
        return ""

    resolved_patient_id = patient_data.get("patient_id") or patient_id
    parts = [f"Patient {resolved_patient_id}"] if resolved_patient_id else []

    vitals = patient_data.get("vitals") or {}
    vitals_parts = []
    if vitals.get("heart_rate") is not None:
        vitals_parts.append(f"HR {round(vitals['heart_rate'])} bpm")
    if vitals.get("temperature") is not None:
        vitals_parts.append(f"Temp {vitals['temperature']:.1f}°F")
    if vitals.get("respiratory_rate") is not None:
        vitals_parts.append(f"RR {round(vitals['respiratory_rate'])}/min")
    if vitals.get("o2_saturation") is not None:
        vitals_parts.append(f"SpO₂ {round(vitals['o2_saturation'])}%")
    if vitals.get("systolic_bp") is not None:
        diastolic = vitals.get("diastolic_bp")
        if diastolic is not None:
            vitals_parts.append(f"BP {round(vitals['systolic_bp'])}/{round(diastolic)} mmHg")
        else:
            vitals_parts.append(f"BP {round(vitals['systolic_bp'])} mmHg")
    if vitals_parts:
        parts.append(f"Vitals: {', '.join(vitals_parts)}")

    diagnoses = patient_data.get("diagnoses") or []
    if diagnoses:
        parts.append(f"Diagnoses: {', '.join(d.get('title', '') for d in diagnoses if d.get('title'))}")

    medications = patient_data.get("medications") or []
    if medications:
        parts.append(f"Current Medications: {', '.join(m.get('name', '') for m in medications if m.get('name'))}")

    if not parts:
        return ""
    return "\n\nPatient clinical context:\n" + "\n".join(parts)


async def _prepare_chat_query(request, session: dict) -> tuple[str, Optional[str]]:
    visible_message = request.message.strip()
    mode = _get_assistant_mode(request, session)
    if mode != "patient":
        return visible_message, None

    if _is_off_topic_patient_question(visible_message):
        return "", PATIENT_ASSISTANT_SCOPE_REPLY

    patient_context = ""
    if request.patient_id:
        patient_data = await asyncio.to_thread(get_patient_data_json, request.patient_id)
        patient_context = _build_patient_portal_context(patient_data, request.patient_id)

    wrapped_message = (
        "[PATIENT PORTAL] You are TrustMed AI's patient visit assistant. "
        "You may only answer questions about this patient's visit, chart, diagnoses, "
        f"medications, vitals, lab results, imaging, symptoms, or care plan.{patient_context}\n\n"
        "If the patient asks for anything outside that scope, do not answer the request. "
        f'Respond exactly with:\n"{PATIENT_ASSISTANT_SCOPE_REPLY}"\n\n'
        f'Patient question: "{visible_message}"\n\n'
        "Explain in plain language at an 8th-grade reading level. Avoid medical jargon. "
        "Be warm, direct, and concise. Use short sentences and bullet points when helpful. "
        "Answer specifically about this patient's data when relevant."
    )
    return wrapped_message, None


def _persist_session_turn(session_id: str, session: dict, request, assistant_response: str):
    visible_message = request.message.strip()
    user_entry = {"role": "user", "content": visible_message}
    img_url = _image_url(request.image_path)
    if img_url:
        user_entry["image"] = img_url

    history = session["messages"]
    history.append(user_entry)
    history.append({"role": "assistant", "content": assistant_response})

    if session["title"] == "New chat" and visible_message:
        session["title"] = _auto_title(visible_message)

    if len(history) > 50:
        session["messages"] = history[-50:]

    _save_session(session_id, session)


# =============================================================================
# Pydantic Models
# =============================================================================

class ChatRequest(BaseModel):
    message: str
    session_id: str = "default"
    image_path: Optional[str] = None
    patient_id: Optional[str] = None
    assistant_mode: Optional[str] = None
    temperature: Optional[float] = None  # 0.0–1.0, overrides default
    model: Optional[str] = None          # OpenRouter model ID override
    vision_model: Optional[str] = None   # Vision model ID override
    persist: bool = True                 # Whether to read/write session history


class ChatResponse(BaseModel):
    response: str
    session_id: str
    title: str


class SOAPRequest(BaseModel):
    session_id: str = "default"
    patient_id: Optional[str] = None


class RenameRequest(BaseModel):
    session_id: str
    title: str


class LinkClinicianUploadRequest(BaseModel):
    image_path: str
    title: Optional[str] = None


class DetectPanelsRequest(BaseModel):
    image_path: str


# =============================================================================
# Endpoints
# =============================================================================

@app.get("/")
async def root():
    return {"message": "TrustMed AI API is running", "version": "2.0.0"}


@app.get("/vision-cache")
async def vision_cache_stats():
    """Get vision result cache statistics."""
    return get_vision_cache_stats()


@app.post("/vision-cache/clear")
async def vision_cache_clear():
    """Clear the vision result cache."""
    clear_vision_cache()
    return {"message": "Vision cache cleared"}


async def _stream_chat(request: ChatRequest):
    """SSE generator that streams pipeline progress + LLM tokens."""
    session_id = request.session_id
    session = _load_session(session_id) if request.persist else {
        "id": session_id,
        "title": "New chat",
        "messages": []
    }
    history = session["messages"]

    query, direct_response = await _prepare_chat_query(request, session)
    if request.image_path and os.path.exists(request.image_path):
        query += f" [ATTACHMENT: {request.image_path}]"

    if direct_response is not None:
        if request.persist:
            _persist_session_turn(session_id, session, request, direct_response)
        done_event = {
            "type": "done",
            "session_id": session_id,
            "title": session["title"],
            "final_response": direct_response
        }
        yield f"data: {json.dumps(done_event)}\n\n"
        return

    final_response = ""
    try:
        async for event in ask_trustmed_streaming(
            query, history,
            temperature=request.temperature,
            model=request.model,
            vision_model=request.vision_model
        ):
            if event["type"] == "done":
                final_response = event.get("final_response", "")
                if request.persist:
                    _persist_session_turn(session_id, session, request, final_response)
                # Send done with session metadata
                done_event = {
                    "type": "done",
                    "session_id": session_id,
                    "title": session["title"],
                    "final_response": final_response
                }
                yield f"data: {json.dumps(done_event)}\n\n"
            else:
                yield f"data: {json.dumps(event)}\n\n"
    except Exception as e:
        yield f"data: {json.dumps({'type': 'error', 'message': str(e)})}\n\n"


@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """Streaming chat endpoint — returns SSE events."""
    return StreamingResponse(
        _stream_chat(request),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no"
        }
    )


@app.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Send a message and get an AI response.
    History is persisted to disk per session.
    """
    session_id = request.session_id
    session = _load_session(session_id) if request.persist else {
        "id": session_id,
        "title": "New chat",
        "messages": []
    }
    history = session["messages"]

    # Build query with image attachment if present
    query, direct_response = await _prepare_chat_query(request, session)
    if request.image_path and os.path.exists(request.image_path):
        query += f" [ATTACHMENT: {request.image_path}]"

    if direct_response is not None:
        response = direct_response
        if request.persist:
            _persist_session_turn(session_id, session, request, response)
        return ChatResponse(
            response=response,
            session_id=session_id,
            title=session["title"]
        )

    # Call TrustMed Brain (already async)
    try:
        response = await ask_trustmed(query, history, temperature=request.temperature, model=request.model, vision_model=request.vision_model)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

    if request.persist:
        _persist_session_turn(session_id, session, request, response)

    return ChatResponse(
        response=response,
        session_id=session_id,
        title=session["title"]
    )


@app.post("/upload-image")
async def upload_image(file: UploadFile = File(...)):
    """
    Upload an image for analysis.
    Uses unique filenames to prevent race conditions.
    """
    _ensure_dirs()

    # Generate unique filename
    ext = os.path.splitext(file.filename or "image.jpg")[1] or ".jpg"
    unique_name = f"scan_{uuid.uuid4().hex[:12]}{ext}"
    save_path = os.path.join(UPLOADS_DIR, unique_name)

    try:
        content = await file.read()
        with open(save_path, "wb") as f:
            f.write(content)
        return {"path": save_path, "filename": file.filename}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/patient/{patient_id}/attachments")
async def list_patient_attachments(patient_id: str):
    """
    Return patient-linked imaging/report attachments sorted newest first.
    """
    try:
        return {"attachments": _list_patient_attachments(patient_id)}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/patient/{patient_id}/attachments")
async def upload_patient_attachment(patient_id: str, file: UploadFile = File(...)):
    """
    Upload a patient-visible image or PDF report.
    """
    mime_type = _normalize_patient_upload_mime_type(file)
    if not mime_type:
        raise HTTPException(status_code=400, detail="Only image files and PDF reports are supported.")

    file_kind = _derive_attachment_kind(mime_type)
    original_filename = _sanitize_path_segment(
        file.filename or f"{file_kind or 'attachment'}",
        f"{file_kind or 'attachment'}",
    )
    ext = os.path.splitext(original_filename)[1]
    if not ext:
        ext = mimetypes.guess_extension(mime_type) or (".pdf" if file_kind == "pdf" else ".jpg")

    save_name = f"{file_kind}_{uuid.uuid4().hex[:12]}{ext.lower()}"
    save_path = os.path.join(_patient_attachment_dir(patient_id), save_name)

    try:
        content = await file.read()
        with open(save_path, "wb") as f:
            f.write(content)

        record = _make_attachment_record(
            patient_id=patient_id,
            stored_path=save_path,
            original_filename=original_filename,
            mime_type=mime_type,
            uploaded_by="patient",
            title=original_filename,
        )
        _append_patient_attachment(record)
        return _serialize_attachment(record)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/patient/{patient_id}/attachments/link-clinician-upload")
async def link_clinician_upload(patient_id: str, request: LinkClinicianUploadRequest):
    """
    Copy an existing clinician upload into a patient-visible imaging record.
    """
    source_path = os.path.realpath(request.image_path or "")
    if not os.path.exists(source_path):
        raise HTTPException(status_code=404, detail="Uploaded file not found.")

    _assert_path_in_uploads(source_path)

    mime_type = _normalize_existing_file_mime_type(source_path)
    if not mime_type:
        raise HTTPException(status_code=400, detail="Only image files and PDF reports can be linked to patient imaging.")

    file_kind = _derive_attachment_kind(mime_type)
    display_name = request.title or os.path.basename(source_path)
    original_filename = _sanitize_path_segment(display_name, os.path.basename(source_path))
    ext = os.path.splitext(original_filename)[1]
    if not ext:
        ext = os.path.splitext(source_path)[1] or mimetypes.guess_extension(mime_type) or ".jpg"

    target_name = f"{file_kind}_{uuid.uuid4().hex[:12]}{ext.lower()}"
    target_path = os.path.join(_patient_attachment_dir(patient_id), target_name)

    try:
        shutil.copyfile(source_path, target_path)
        record = _make_attachment_record(
            patient_id=patient_id,
            stored_path=target_path,
            original_filename=original_filename,
            mime_type=mime_type,
            uploaded_by="clinician",
            title=display_name,
        )
        _append_patient_attachment(record)
        return _serialize_attachment(record)
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/soap-note")
async def soap_note(request: SOAPRequest):
    """
    Generate a structured SOAP note from the current session.
    Returns JSON with subjective, objective, assessment, plan sections.
    """
    session = _load_session(request.session_id)
    history = session["messages"]

    if not history:
        raise HTTPException(status_code=400, detail="No conversation history found")

    try:
        patient_context = "N/A"
        if request.patient_id:
            patient_context = await asyncio.to_thread(get_patient_context, request.patient_id)
            if not patient_context:
                patient_context = f"No patient context found for ID {request.patient_id}"

        note = await asyncio.to_thread(generate_soap_note, history, patient_context, "N/A")
        if "error" in note:
            raise HTTPException(status_code=400, detail=note["error"])
        return note
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/patient/{patient_id}")
async def get_patient(patient_id: str):
    """
    Get structured patient data (vitals, diagnoses, medications) from MIMIC DB.
    """
    try:
        data = await asyncio.to_thread(get_patient_data_json, patient_id)
        if not data.get("vitals") and not data.get("diagnoses") and not data.get("medications"):
            raise HTTPException(status_code=404, detail=f"No data found for patient {patient_id}")
        return data
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/clear-session")
async def clear_session(session_id: str = "default"):
    """
    Delete a chat session from disk (legacy endpoint).
    """
    _delete_session(session_id)
    return {"message": "Session cleared", "session_id": session_id}


@app.delete("/sessions/{session_id}")
async def delete_session(session_id: str):
    """
    Delete a chat session by ID.
    """
    _delete_session(session_id)
    return {"message": "Session deleted", "session_id": session_id}


@app.get("/sessions")
async def list_sessions(source: str = None):
    """
    List all saved sessions with metadata, optionally filtered by source.
    """
    all_sessions = _list_all_sessions()
    if source:
        all_sessions = [s for s in all_sessions if s.get("source") == source]
    return {"sessions": all_sessions}


@app.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """
    Get full message history for a session.
    """
    session = _load_session(session_id)
    return session


@app.post("/sessions/rename")
async def rename_session(request: RenameRequest):
    """
    Rename a chat session.
    """
    session = _load_session(request.session_id)
    session["title"] = request.title
    _save_session(request.session_id, session)
    return {"message": "Session renamed", "title": request.title}


@app.post("/sessions/new")
async def create_session(source: str = "clinician"):
    """
    Create a new empty session and return its ID.
    """
    session_id = uuid.uuid4().hex[:16]
    session = {
        "id": session_id,
        "title": "New chat",
        "created_at": time.time(),
        "updated_at": time.time(),
        "messages": [],
        "source": source
    }
    _save_session(session_id, session)
    return session


# =============================================================================
# Knowledge Graph & Panel Detection Endpoints
# =============================================================================

PANELS_DIR = os.path.join(UPLOADS_DIR, "panels")


def _get_graph_data(search_term: str, patient_id: str = None) -> dict:
    """Fetch graph data from Neo4j as plain JSON."""
    try:
        from src.graph_visualizer import get_graph_json
        return get_graph_json(search_term, patient_id)
    except Exception as e:
        print(f"Graph query error: {e}")
        err_msg = str(e).lower()
        if any(token in err_msg for token in ("routing", "connect", "certificate", "ssl", "neo4j")):
            return {
                "nodes": [],
                "edges": [],
                "stats": {},
                "error": "Knowledge graph unavailable. Check Neo4j connectivity and local SSL certificates.",
            }
        return {
            "nodes": [],
            "edges": [],
            "stats": {},
            "error": "Unable to load graph data.",
        }


@app.get("/graph")
async def get_graph(search_term: str = Query(..., min_length=2), patient_id: str = None):
    """
    Get knowledge graph data for a search term.
    Returns nodes and edges as plain JSON for frontend rendering.
    """
    try:
        data = await asyncio.to_thread(_get_graph_data, search_term, patient_id)
        return data
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.post("/detect-panels")
async def detect_panels(request: DetectPanelsRequest):
    """
    Detect if an image is a compound figure and split into panels.
    Saves each panel as a separate PNG in uploads/panels/.
    """
    image_path = request.image_path
    if not os.path.exists(image_path):
        raise HTTPException(status_code=404, detail="Image file not found")

    try:
        # Run detection in thread (OpenCV is CPU-bound)
        analysis = await asyncio.to_thread(detect_compound_figure, image_path)

        result = {
            "is_compound": analysis.is_compound,
            "confidence": round(analysis.confidence, 3),
            "num_panels": analysis.num_panels,
            "layout": analysis.layout.value if analysis.layout else "single",
            "grid_structure": analysis.grid_structure,
            "panels": []
        }

        if analysis.is_compound:
            # Split and save each panel
            os.makedirs(PANELS_DIR, exist_ok=True)
            subfigures = await asyncio.to_thread(split_compound_figure, image_path)

            for sf in subfigures:
                panel_filename = f"panel_{uuid.uuid4().hex[:8]}_{sf.panel_id}.png"
                panel_path = os.path.join(PANELS_DIR, panel_filename)
                sf.image.save(panel_path)

                result["panels"].append({
                    "panel_id": sf.panel_id,
                    "label": sf.label or sf.panel_id,
                    "image_url": f"/panels/{panel_filename}",
                    "bbox": {
                        "x1": sf.bbox.x1, "y1": sf.bbox.y1,
                        "x2": sf.bbox.x2, "y2": sf.bbox.y2,
                        "width": sf.bbox.width, "height": sf.bbox.height
                    },
                    "grid_position": list(sf.grid_position),
                    "confidence": round(sf.confidence, 3)
                })

        return result
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@app.get("/panels/{filename}")
async def serve_panel(filename: str):
    """Serve a split panel image."""
    filepath = os.path.join(PANELS_DIR, filename)
    if not os.path.exists(filepath):
        raise HTTPException(status_code=404, detail="Panel image not found")
    return FileResponse(filepath, media_type="image/png")


# =============================================================================
# Patient Portal Endpoints
# =============================================================================

# In-memory cache for term explanations (persists across requests)
_term_cache: Dict[str, str] = {}

PATIENT_SUMMARY_PROMPT = """You are a friendly medical assistant explaining health information to a patient.
Translate all clinical terms to plain English. Use an 8th-grade reading level.
Be warm, clear, and reassuring. Do not diagnose or give medical advice — just explain what the existing data means.

Given the following patient clinical data, return a JSON object with exactly these keys:
- "summary": A 2-3 sentence overview of the patient's current health status in plain language.
- "vitals_explanation": Explain what each vital sign means and whether it's in a healthy range. Be reassuring.
- "medications_explanation": For each medication, explain what it's for in simple terms.
- "next_steps": 2-3 practical next steps the patient should be aware of (follow-ups, things to watch for, etc.)

Respond ONLY with valid JSON. No markdown, no code fences, no extra text.

Patient Data:
{patient_data}"""


def _normalize_next_steps(value) -> List[str]:
    """Coerce mixed LLM output into a clean list of brief next-step strings."""
    parsed = _parse_loose_literal(value)
    if isinstance(parsed, list):
        return [str(item).strip() for item in parsed if str(item).strip()]

    if isinstance(value, list):
        return [str(item).strip() for item in value if str(item).strip()]

    if isinstance(value, str):
        candidates = []
        for raw_line in value.splitlines():
            line = raw_line.strip().lstrip("-*•0123456789. )").strip()
            if line:
                candidates.append(line)
        if candidates:
            return candidates[:5]
        if value.strip():
            return [value.strip()]

    return []


def _parse_loose_literal(value):
    """Parse JSON or Python-literal strings that the LLM sometimes returns inside JSON fields."""
    if isinstance(value, (dict, list)):
        return value
    if not isinstance(value, str):
        return value

    stripped = value.strip()
    if not stripped or stripped[0] not in "[{":
        return value

    for parser in (json.loads, ast.literal_eval):
        try:
            parsed = parser(stripped)
        except Exception:
            continue
        if isinstance(parsed, (dict, list)):
            return parsed

    return value


def _normalize_vitals_explanation(value) -> str:
    """Flatten structured vitals payloads into plain prose."""
    parsed = _parse_loose_literal(value)

    if isinstance(parsed, dict):
        ordered_keys = [
            "temperature",
            "heart_rate",
            "respiratory_rate",
            "o2_saturation",
            "systolic_bp",
            "diastolic_bp",
        ]
        pieces = []
        seen = set()

        for key in ordered_keys:
            text = str(parsed.get(key) or "").strip()
            if text and text not in seen:
                seen.add(text)
                pieces.append(text)

        for key, raw in parsed.items():
            if key in ordered_keys:
                continue
            text = str(raw or "").strip()
            if text and text not in seen:
                seen.add(text)
                pieces.append(text)

        return " ".join(pieces)

    if isinstance(parsed, list):
        return " ".join(str(item).strip() for item in parsed if str(item).strip())

    return str(value or "").strip()


def _normalize_medications_explanation(value) -> str:
    """Flatten structured medication payloads into semicolon-separated plain-language items."""
    parsed = _parse_loose_literal(value)

    if isinstance(parsed, list):
        items = []
        for entry in parsed:
            if isinstance(entry, dict):
                name = str(entry.get("name") or "").strip()
                explanation = str(entry.get("explanation") or entry.get("description") or "").strip()
                if name and explanation:
                    items.append(f"{name}: {explanation}")
                elif explanation:
                    items.append(explanation)
                elif name:
                    items.append(name)
            else:
                text = str(entry).strip()
                if text:
                    items.append(text)
        return "; ".join(items)

    if isinstance(parsed, dict):
        items = []
        for key, raw in parsed.items():
            text = str(raw or "").strip()
            label = str(key or "").replace("_", " ").strip()
            if label and text:
                items.append(f"{label}: {text}")
            elif text:
                items.append(text)
        return "; ".join(items)

    return str(value or "").strip()


def _normalize_patient_summary_payload(payload) -> dict:
    """Return a stable frontend-safe summary payload regardless of LLM formatting."""
    if not isinstance(payload, dict):
        payload = {}

    next_steps = _normalize_next_steps(payload.get("next_steps"))
    if not next_steps:
        next_steps = [
            "Review these results with your care team at your next visit.",
            "Ask your clinician if any follow-up tests or medication changes are needed.",
        ]

    return {
        "summary": str(payload.get("summary") or "We could not generate a detailed summary right now.").strip(),
        "vitals_explanation": _normalize_vitals_explanation(
            payload.get("vitals_explanation")
            or "Your vital signs are available in your chart, but a plain-language explanation was not generated."
        ),
        "medications_explanation": _normalize_medications_explanation(
            payload.get("medications_explanation")
            or "Your medication list is available in your chart, but a plain-language explanation was not generated."
        ),
        "next_steps": next_steps,
    }


def _is_placeholder_summary_text(value: str) -> bool:
    """Detect generic fallback strings that should not be shown as patient content."""
    if not isinstance(value, str):
        return True

    normalized = value.strip().lower()
    if not normalized:
        return True

    placeholders = [
        "explanation unavailable. please consult your physician.",
        "we could not generate a detailed summary right now.",
        "unable to generate summary.",
        "please ask your care team about your vital signs.",
        "please review your medications with your care team.",
        "plain-language explanation was not generated.",
    ]
    return any(phrase in normalized for phrase in placeholders)


def _friendly_condition_name(title: str) -> str:
    """Translate common diagnosis labels into more patient-friendly names."""
    raw = (title or "").strip()
    lower = raw.lower()

    replacements = [
        ("pneumonia", "a lung infection"),
        ("hypercholesterolemia", "high cholesterol"),
        ("hypertension", "high blood pressure"),
        ("hypothyroidism", "low thyroid function"),
        ("respiratory failure", "a breathing problem"),
        ("pleural effusion", "fluid around the lungs"),
        ("gastrointestinal hemorrhage", "bleeding in the stomach or intestines"),
        ("gastroenteritis", "stomach or bowel irritation"),
        ("cough", "a cough"),
        ("laryngitis", "voice box irritation"),
        ("femur", "a hip or thigh bone injury"),
    ]
    for needle, replacement in replacements:
        if needle in lower:
            return replacement

    cleaned = raw.replace("_", " ").replace(",", ", ")
    if cleaned.isupper():
        cleaned = cleaned.title()
    return cleaned


def _describe_vitals(vitals: dict) -> List[str]:
    """Create brief plain-language statements for the latest vitals."""
    if not vitals:
        return ["Your chart does not show any recent vital signs yet."]

    statements: List[str] = []

    heart_rate = vitals.get("heart_rate")
    if isinstance(heart_rate, (int, float)):
        if 60 <= heart_rate <= 100:
            statements.append(f"Your heart rate was {round(heart_rate)} beats per minute, which is in a usual adult range.")
        elif heart_rate > 100:
            statements.append(f"Your heart rate was {round(heart_rate)} beats per minute, which is a little faster than expected.")
        else:
            statements.append(f"Your heart rate was {round(heart_rate)} beats per minute, which is a little lower than usual.")

    oxygen = vitals.get("o2_saturation")
    if isinstance(oxygen, (int, float)):
        if oxygen >= 95:
            statements.append(f"Your oxygen level was {round(oxygen)}%, which is reassuring.")
        elif oxygen >= 90:
            statements.append(f"Your oxygen level was {round(oxygen)}%, which is slightly below the ideal range and worth watching.")
        else:
            statements.append(f"Your oxygen level was {round(oxygen)}%, which is lower than expected.")

    systolic = vitals.get("systolic_bp")
    diastolic = vitals.get("diastolic_bp")
    if isinstance(systolic, (int, float)) and isinstance(diastolic, (int, float)):
        if systolic >= 140:
            statements.append(f"Your blood pressure was {round(systolic)}/{round(diastolic)}, which is on the high side.")
        elif systolic < 90:
            statements.append(f"Your blood pressure was {round(systolic)}/{round(diastolic)}, which is a bit low.")
        else:
            statements.append(f"Your blood pressure was {round(systolic)}/{round(diastolic)}, which is in an acceptable range.")

    temperature = vitals.get("temperature")
    if isinstance(temperature, (int, float)):
        if 97 <= temperature <= 99:
            statements.append(f"Your temperature was {temperature:.1f} degrees Fahrenheit, which is within a typical range.")
        elif temperature > 100.4:
            statements.append(f"Your temperature was {temperature:.1f} degrees Fahrenheit, which can suggest a fever.")
        else:
            statements.append(f"Your temperature was {temperature:.1f} degrees Fahrenheit.")

    respiratory_rate = vitals.get("respiratory_rate")
    if isinstance(respiratory_rate, (int, float)):
        if 12 <= respiratory_rate <= 20:
            statements.append(f"Your breathing rate was {round(respiratory_rate)} breaths per minute, which is within a common adult range.")
        elif respiratory_rate > 20:
            statements.append(f"Your breathing rate was {round(respiratory_rate)} breaths per minute, which is a little faster than usual.")
        else:
            statements.append(f"Your breathing rate was {round(respiratory_rate)} breaths per minute, which is a little slower than usual.")

    return statements or ["Your care team has recent vital signs on file, but there was not enough detail to summarize them cleanly."]


def _describe_medications(medications: list) -> str:
    """Explain charted medications in plain language without relying on the LLM."""
    if not medications:
        return "There are no active medications listed in your chart right now."

    explanation_map = [
        ("ace inhibitor", "often used to support blood pressure and heart health"),
        ("diuretic", "used to help the body remove extra fluid"),
        ("corticosteroid", "used to calm inflammation"),
        ("gastric acid", "used to lower stomach acid and reduce irritation"),
        ("proton pump inhibitor", "used to lower stomach acid and reduce irritation"),
        ("histamine h2-receptor antagonist", "used to reduce stomach acid"),
        ("antidepressant", "used to support mood and sometimes sleep or appetite"),
        ("adhd", "used to support focus and alertness"),
        ("stimulant", "used to support focus and alertness"),
        ("analgesic", "used for pain relief"),
        ("antipyretic", "used to reduce fever or body aches"),
    ]

    parts: List[str] = []
    for med in medications[:4]:
        name = str(med.get("name") or "This medicine").strip()
        desc = str(med.get("description") or "").strip()
        desc_lower = desc.lower()

        explanation = None
        for needle, friendly in explanation_map:
            if needle in desc_lower:
                explanation = friendly
                break

        if explanation:
            parts.append(f"{name} is {explanation}.")
        elif desc:
            parts.append(f"{name} is listed in your chart as {desc.lower()}.")
        else:
            parts.append(f"{name} is one of the medicines currently listed in your chart.")

    if len(medications) > 4:
        parts.append(f"Your chart also lists {len(medications) - 4} additional medicines.")

    return " ".join(parts)


def _build_patient_summary_fallback(patient_data: dict) -> dict:
    """Build a patient-specific summary without depending on an external model call."""
    vitals = patient_data.get("vitals") or {}
    diagnoses = patient_data.get("diagnoses") or []
    medications = patient_data.get("medications") or []

    diagnosis_names: List[str] = []
    for diagnosis in diagnoses:
        friendly = _friendly_condition_name(diagnosis.get("title", ""))
        if friendly and friendly not in diagnosis_names:
            diagnosis_names.append(friendly)

    abnormal_flags: List[str] = []
    oxygen = vitals.get("o2_saturation")
    systolic = vitals.get("systolic_bp")
    respiratory_rate = vitals.get("respiratory_rate")
    temperature = vitals.get("temperature")

    if isinstance(oxygen, (int, float)) and oxygen < 95:
        abnormal_flags.append("a slightly low oxygen level")
    if isinstance(systolic, (int, float)) and systolic >= 140:
        abnormal_flags.append("higher blood pressure")
    if isinstance(respiratory_rate, (int, float)) and respiratory_rate > 20:
        abnormal_flags.append("a faster breathing rate")
    if isinstance(temperature, (int, float)) and temperature > 100.4:
        abnormal_flags.append("a fever")

    if diagnosis_names:
        top_conditions = ", ".join(diagnosis_names[:3])
        summary = f"Your chart shows active health issues including {top_conditions}."
    else:
        summary = "Your chart includes recent health information from your care team."

    if abnormal_flags:
        if len(abnormal_flags) == 1:
            summary += f" Your most recent vital signs also show {abnormal_flags[0]}, so your team is likely watching that closely."
        else:
            summary += f" Your most recent vital signs show {', '.join(abnormal_flags[:-1])} and {abnormal_flags[-1]}, so those areas may need closer follow-up."
    elif vitals:
        summary += " Your latest vital signs are mostly within a reassuring range."
    elif medications:
        summary += " Your current medicine list is also available in the chart."

    next_steps: List[str] = []
    if abnormal_flags:
        next_steps.append("Ask whether your recent vital signs should be rechecked soon.")
    if medications:
        next_steps.append("Bring your medication list to your next visit and ask what each medicine is for.")
    if any("lung infection" in item or "breathing problem" in item or "fluid around the lungs" in item for item in diagnosis_names):
        next_steps.append("Tell your care team right away if breathing feels worse, especially if you are more short of breath than usual.")
    next_steps.append("Keep your next follow-up appointment so your care team can review these results with you.")

    deduped_steps: List[str] = []
    for step in next_steps:
        if step not in deduped_steps:
            deduped_steps.append(step)

    return {
        "summary": summary,
        "vitals_explanation": " ".join(_describe_vitals(vitals)),
        "medications_explanation": _describe_medications(medications),
        "next_steps": deduped_steps[:4],
    }


def _merge_summary_with_fallback(payload: dict, fallback: dict) -> dict:
    """Use the model output when available, but replace placeholders with local patient-specific text."""
    merged = _normalize_patient_summary_payload(payload)
    for key in ("summary", "vitals_explanation", "medications_explanation"):
        if _is_placeholder_summary_text(merged.get(key)):
            merged[key] = fallback[key]

    if not merged.get("next_steps"):
        merged["next_steps"] = fallback["next_steps"]

    return merged


@app.post("/patient/{patient_id}/summary")
async def patient_summary(patient_id: str):
    """
    Generate a plain-language health summary for a patient.
    Uses the LLM to translate clinical data into patient-friendly explanations.
    """
    try:
        # Get raw clinical data
        patient_data = await asyncio.to_thread(get_patient_data_json, patient_id)
        if not patient_data or "error" in str(patient_data).lower():
            raise HTTPException(status_code=404, detail="Patient not found")

        fallback_result = _build_patient_summary_fallback(patient_data)

        # Format the data as a readable string for the LLM
        data_str = json.dumps(patient_data, indent=2, default=str)

        # Use the direct path here; this endpoint only needs summarization, not full RAG.
        prompt = PATIENT_SUMMARY_PROMPT.format(patient_data=data_str)
        response = await ask_trustmed_direct(prompt)

        if _is_placeholder_summary_text(response):
            return fallback_result

        # Try to parse as JSON; if it fails, wrap in a structured response
        try:
            # Strip markdown code fences if present
            cleaned = response.strip()
            if cleaned.startswith("```"):
                cleaned = cleaned.split("\n", 1)[1]  # Remove first line
                if cleaned.endswith("```"):
                    cleaned = cleaned[:-3]
                cleaned = cleaned.strip()
            result = _merge_summary_with_fallback(json.loads(cleaned), fallback_result)
        except (json.JSONDecodeError, ValueError):
            # LLM didn't return valid JSON — fall back to local patient-specific content.
            result = fallback_result

        return result

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Summary generation failed: {str(e)}")



from medical_dictionary import MEDICAL_DICTIONARY, get_medical_explanation

EXPLAIN_TERM_PROMPT = """You are a medical dictionary and clinical summarizer. 
Explain the term "{term}" in a way that is clear for clinicians but understandable for patients.
Provide a 2-3 sentence definition.

Respond with valid JSON including:
- "definition": A plain-English explanation (8th grade level).
- "clinician_note": A brief technical note for healthcare providers (optional, if applicable).
- "source": "AI Library"
"""

EXPLAIN_TERM_FALLBACK = "Explanation unavailable. Please consult your physician."


@app.get("/explain-term")
async def explain_term(term: str = Query(..., min_length=2, max_length=200)):
    """
    Explain a medical term using a local dictionary or an LLM.
    """
    cache_key = term.strip().lower()
    
    # 1. Local Dictionary Check (Instant)
    local_data = get_medical_explanation(cache_key)
    if local_data:
        return {
            "term": term, 
            "explanation": local_data["definition"],
            "clinician_note": local_data.get("clinician_note"),
            "source": "Medical Dictionary",
            "cached": True
        }

    # 2. LRU Cache Check
    cached_explanation = _term_cache.get(cache_key)
    if cached_explanation and cached_explanation != EXPLAIN_TERM_FALLBACK:
        return {"term": term, "explanation": cached_explanation, "source": "AI Library", "cached": True}

    # 3. External API Fallbacks (Replaces Rate-limited AI)
    import urllib.request
    import urllib.parse
    import urllib.error

    def fetch_definitions():
        # First try Free Dictionary API
        try:
            url = f"https://api.dictionaryapi.dev/api/v2/entries/en/{urllib.parse.quote(term)}"
            req = urllib.request.Request(url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                if data and isinstance(data, list) and len(data) > 0:
                    meanings = data[0].get("meanings", [])
                    if meanings:
                        definitions = meanings[0].get("definitions", [])
                        if definitions:
                            return definitions[0].get("definition"), "English Dictionary"
        except Exception:
            pass

        # If not found, try Wikipedia Open Search
        try:
            search_url = f"https://en.wikipedia.org/w/api.php?action=query&list=search&srsearch={urllib.parse.quote(term)}&utf8=&format=json"
            req = urllib.request.Request(search_url, headers={'User-Agent': 'Mozilla/5.0'})
            with urllib.request.urlopen(req, timeout=3) as resp:
                data = json.loads(resp.read().decode('utf-8'))
                results = data.get("query", {}).get("search", [])
                if results:
                    title = results[0]["title"]
                    # Fetch short extract
                    extract_url = f"https://en.wikipedia.org/w/api.php?action=query&prop=extracts&exsentences=2&exlimit=1&titles={urllib.parse.quote(title)}&explaintext=1&format=json&formatversion=2"
                    req2 = urllib.request.Request(extract_url, headers={'User-Agent': 'Mozilla/5.0'})
                    with urllib.request.urlopen(req2, timeout=3) as resp2:
                        data2 = json.loads(resp2.read().decode('utf-8'))
                        pages = data2.get("query", {}).get("pages", [])
                        if pages and "extract" in pages[0] and pages[0]["extract"].strip():
                            return pages[0]["extract"].strip(), "Wikipedia Glossary"
        except Exception:
            pass
            
        return None, None

    try:
        explanation, source = await asyncio.to_thread(fetch_definitions)
        
        if explanation:
            if explanation != EXPLAIN_TERM_FALLBACK:
                _term_cache[cache_key] = explanation

            return {
                "term": term, 
                "explanation": explanation, 
                "clinician_note": None,
                "source": source,
                "cached": False
            }

        # Final fallback
        return {"term": term, "explanation": "Term not found in English or medical dictionary.", "source": "System"}

    except Exception as e:
        # Emergency fallback to allow app to continue
        return {"term": term, "explanation": "Explanation unavailable.", "source": "System", "error": str(e)}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
