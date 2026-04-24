"""
Central runtime configuration for TrustMed AI.

Keep filesystem paths absolute so the backend behaves the same whether it is
started from the project root, api/, a test runner, or a helper script.
"""

from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv


def _bool_env(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None:
        return default
    return value.strip().lower() in {"1", "true", "yes", "on"}


def _int_env(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        return default
    try:
        return int(str(value).strip())
    except ValueError:
        return default


PROJECT_ROOT_PATH = Path(__file__).resolve().parents[1]
PROJECT_ROOT = str(PROJECT_ROOT_PATH)
load_dotenv(PROJECT_ROOT_PATH / ".env")


def _rooted_path_env(name: str, default: Path) -> Path:
    value = os.getenv(name)
    candidate = Path(value).expanduser() if value else default
    if not candidate.is_absolute():
        candidate = PROJECT_ROOT_PATH / candidate
    return candidate.resolve()


DATA_DIR_PATH = _rooted_path_env("TRUSTMED_DATA_DIR", PROJECT_ROOT_PATH / "data")
DATA_DIR = str(DATA_DIR_PATH)

CHROMA_DB_DIR_PATH = _rooted_path_env("CHROMA_DB_DIR", DATA_DIR_PATH / "chroma_db")
CHROMA_DB_DIR = str(CHROMA_DB_DIR_PATH)

UPLOADS_DIR_PATH = _rooted_path_env("TRUSTMED_UPLOADS_DIR", PROJECT_ROOT_PATH / "uploads")
UPLOADS_DIR = str(UPLOADS_DIR_PATH)

STORAGE_DIR_PATH = _rooted_path_env("TRUSTMED_STORAGE_DIR", PROJECT_ROOT_PATH / "storage")
STORAGE_DIR = str(STORAGE_DIR_PATH)

PATIENT_FILES_DIR_PATH = UPLOADS_DIR_PATH / "patient-files"
PATIENT_FILES_DIR = str(PATIENT_FILES_DIR_PATH)

PATIENT_FILES_REGISTRY_PATH = STORAGE_DIR_PATH / "patient_files.json"
PATIENT_FILES_REGISTRY = str(PATIENT_FILES_REGISTRY_PATH)

CHAT_HISTORY_DIR_PATH = PROJECT_ROOT_PATH / "chat_history"
CHAT_HISTORY_DIR = str(CHAT_HISTORY_DIR_PATH)


# Model budgets. OpenRouter accepts max_tokens/max_completion_tokens; LangChain's
# ChatOpenAI still exposes max_tokens and maps it through for compatible APIs.
CHAT_MAX_TOKENS = _int_env("CHAT_MAX_TOKENS", 1400)
STREAM_MAX_TOKENS = _int_env("STREAM_MAX_TOKENS", 1400)
GRAPH_MAX_TOKENS = _int_env("GRAPH_MAX_TOKENS", 400)
SAFETY_MAX_TOKENS = _int_env("SAFETY_MAX_TOKENS", 700)
SOAP_MAX_TOKENS = _int_env("SOAP_MAX_TOKENS", 1200)
DIRECT_MAX_TOKENS = _int_env("DIRECT_MAX_TOKENS", 500)
REPORT_OCR_MAX_TOKENS = _int_env("REPORT_OCR_MAX_TOKENS", 1200)
VISION_MAX_TOKENS = _int_env("VISION_MAX_TOKENS", 400)
VERTEX_VISION_MAX_TOKENS = _int_env("VERTEX_VISION_MAX_TOKENS", 500)


# Timeouts and toggles.
GRAPH_TIMEOUT_SECONDS = _int_env("GRAPH_TIMEOUT_SECONDS", 20)
VECTOR_TIMEOUT_SECONDS = _int_env("VECTOR_TIMEOUT_SECONDS", 10)
DRUG_SAFETY_TIMEOUT_SECONDS = _int_env("DRUG_SAFETY_TIMEOUT_SECONDS", 10)
SAFETY_TIMEOUT_SECONDS = _int_env("SAFETY_TIMEOUT_SECONDS", 30)
SYNTHESIS_TIMEOUT_SECONDS = _int_env("SYNTHESIS_TIMEOUT_SECONDS", 40)
RETRIEVAL_CACHE_TTL_SECONDS = _int_env("RETRIEVAL_CACHE_TTL_SECONDS", 300)

TRUSTMED_QUALITY_MODE = _bool_env("TRUSTMED_QUALITY_MODE", False)
ENABLE_LLM_GRAPH = _bool_env("ENABLE_LLM_GRAPH", False)
ENABLE_VISUAL_RAG = _bool_env("ENABLE_VISUAL_RAG", False)

TRUSTMED_SAFETY_MODE = os.getenv("TRUSTMED_SAFETY_MODE", "balanced").strip().lower()
if TRUSTMED_SAFETY_MODE not in {"off", "balanced", "strict"}:
    TRUSTMED_SAFETY_MODE = "balanced"

VISION_PROVIDER = os.getenv("VISION_PROVIDER", "openrouter").strip().lower()
if VISION_PROVIDER not in {"openrouter", "vertex"}:
    VISION_PROVIDER = "openrouter"
