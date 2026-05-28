#!/usr/bin/env python3
"""
Validate and optionally repair local TrustMed runtime state.

Default mode is read-only. Use --repair to back up and rewrite
storage/patient_files.json by pruning missing files and registering real
patient files found under uploads/patient-files/<patient_id>/.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import mimetypes
import os
import shutil
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(PROJECT_ROOT))

from src.runtime_config import (  # noqa: E402
    CHROMA_DB_DIR,
    PATIENT_FILES_DIR,
    PATIENT_FILES_REGISTRY,
    STORAGE_DIR,
    UPLOADS_DIR,
    ENABLE_VISUAL_RAG,
    VISION_PROVIDER,
)


def _utc_iso_from_mtime(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, timezone.utc).isoformat().replace("+00:00", "Z")


def _load_registry() -> list[dict[str, Any]]:
    registry_path = Path(PATIENT_FILES_REGISTRY)
    if not registry_path.exists():
        return []
    try:
        data = json.loads(registry_path.read_text())
    except json.JSONDecodeError:
        return []
    return data if isinstance(data, list) else []


def _write_registry(records: list[dict[str, Any]]) -> Path:
    registry_path = Path(PATIENT_FILES_REGISTRY)
    registry_path.parent.mkdir(parents=True, exist_ok=True)
    backup_path = registry_path.with_suffix(
        registry_path.suffix + f".bak-{datetime.now().strftime('%Y%m%d-%H%M%S')}"
    )
    if registry_path.exists():
        shutil.copy2(registry_path, backup_path)
    else:
        backup_path.write_text("[]\n")
    registry_path.write_text(json.dumps(records, indent=2) + "\n")
    return backup_path


def _url_to_path(url: str) -> Path | None:
    prefix = "/uploads/"
    if not url or not str(url).startswith(prefix):
        return None
    return Path(UPLOADS_DIR) / str(url)[len(prefix):]


def _uploads_url(path: Path) -> str:
    rel = path.resolve().relative_to(Path(UPLOADS_DIR).resolve())
    return "/uploads/" + str(rel).replace(os.sep, "/")


def _attachment_kind(mime_type: str) -> str | None:
    if mime_type.startswith("image/"):
        return "image"
    if mime_type == "application/pdf":
        return "pdf"
    return None


def _is_attachment_file(path: Path) -> bool:
    if not path.is_file() or path.name.endswith(".report.json"):
        return False
    mime_type, _ = mimetypes.guess_type(path.name)
    return bool(mime_type and _attachment_kind(mime_type))


def _make_recovered_record(path: Path) -> dict[str, Any]:
    mime_type, _ = mimetypes.guess_type(path.name)
    mime_type = mime_type or "application/octet-stream"
    file_kind = _attachment_kind(mime_type)
    patient_id = path.parent.name
    title = path.stem.replace("_", " ").replace("-", " ").strip() or path.name
    return {
        "id": uuid.uuid4().hex[:16],
        "patient_id": patient_id,
        "title": title,
        "original_filename": path.name,
        "mime_type": mime_type,
        "file_kind": file_kind,
        "uploaded_by": "recovered",
        "uploaded_at": _utc_iso_from_mtime(path),
        "url": _uploads_url(path),
    }


def check_chroma() -> tuple[bool, list[str]]:
    messages: list[str] = []
    if importlib.util.find_spec("chromadb") is None:
        return False, ["Chroma: chromadb package is not installed."]
    try:
        import chromadb

        client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
        collections = client.list_collections()
        counts = []
        for collection in collections:
            counts.append(f"{collection.name}={client.get_collection(collection.name).count()}")
        messages.append("Chroma: " + (", ".join(counts) if counts else "no collections found"))
        expected = {"symptoms", "medicines", "diseases", "medical_images"}
        found = {collection.name for collection in collections}
        return expected.issubset(found), messages
    except Exception as exc:
        return False, [f"Chroma error: {exc}"]


def check_optional_deps() -> list[str]:
    messages = []
    try:
        google_auth = importlib.util.find_spec("google.auth") is not None
    except ModuleNotFoundError:
        google_auth = False
    try:
        open_clip = importlib.util.find_spec("open_clip") is not None
    except ModuleNotFoundError:
        open_clip = False

    messages.append(f"Vertex: provider={VISION_PROVIDER}, google-auth={'ok' if google_auth else 'missing'}")
    messages.append(
        f"Visual-RAG: enabled={ENABLE_VISUAL_RAG}, open_clip={'ok' if open_clip else 'missing'}"
    )
    return messages


def validate_registry(repair: bool) -> tuple[bool, list[str]]:
    messages: list[str] = []
    records = _load_registry()
    missing: list[dict[str, Any]] = []
    kept: list[dict[str, Any]] = []
    registered_urls = set()

    for record in records:
        path = _url_to_path(str(record.get("url") or ""))
        if path and path.exists():
            kept.append(record)
            registered_urls.add(str(path.resolve()))
        else:
            missing.append(record)

    patient_root = Path(PATIENT_FILES_DIR)
    real_patient_files = [
        path
        for path in patient_root.rglob("*")
        if _is_attachment_file(path)
    ] if patient_root.exists() else []
    unregistered = [
        path for path in real_patient_files
        if str(path.resolve()) not in registered_urls
    ]

    messages.append(
        f"Patient registry: records={len(records)}, existing={len(kept)}, "
        f"missing={len(missing)}, unregistered_patient_files={len(unregistered)}"
    )

    if repair and (missing or unregistered):
        repaired = list(kept)
        repaired.extend(_make_recovered_record(path) for path in sorted(unregistered))
        repaired.sort(key=lambda item: item.get("uploaded_at") or "", reverse=True)
        backup = _write_registry(repaired)
        messages.append(f"Repair: wrote {len(repaired)} records, backup={backup}")
        records = repaired
        missing = []

    nested_storage = Path(STORAGE_DIR) / "storage"
    nested_uploads = Path(STORAGE_DIR) / "uploads"
    if nested_storage.exists() or nested_uploads.exists():
        messages.append("Warning: nested storage artifacts found under storage/; leave ignored or remove manually.")

    root_upload_files = [
        path for path in Path(UPLOADS_DIR).glob("*")
        if path.is_file() and _is_attachment_file(path)
    ] if Path(UPLOADS_DIR).exists() else []
    if root_upload_files:
        messages.append(f"Info: {len(root_upload_files)} root clinician upload(s) are not patient registry entries.")

    return not missing, messages


def main() -> int:
    parser = argparse.ArgumentParser(description="Validate TrustMed runtime state.")
    parser.add_argument("--repair", action="store_true", help="repair patient_files.json with a backup")
    args = parser.parse_args()

    ok_chroma, chroma_messages = check_chroma()
    ok_registry, registry_messages = validate_registry(args.repair)
    optional_messages = check_optional_deps()

    for message in chroma_messages + registry_messages + optional_messages:
        print(message)

    return 0 if ok_chroma and ok_registry else 1


if __name__ == "__main__":
    raise SystemExit(main())

