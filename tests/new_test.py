#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Agentic RAG Orchestrator for Chroma + Sentence-Transformers

- Loops over every Chroma collection in a persistent DB path.
- Spawns an agent per collection. Each agent:
  * Retrieves via embedding similarity.
  * Uses a two-threshold band (X, Y) to decide:
      - strong hits (>= X) -> keep;
      - borderline (Y <= sim < X) -> keep only if metadata is relevant (LLM or heuristic).
  * Summarizes selected evidence verbosely with citations.
- The orchestrator:
  * Runs agents in parallel.
  * For each agent, iteratively adjusts (X, Y) under a time budget if needed.
  * Merges agent reports into a single cited answer.

Pluggable components:
- EmbeddingsProvider (default: SentenceTransformer "sentence-transformers/all-MiniLM-L6-v2")
- LLMProvider (default: LocalHeuristicLLM; optional: OpenAIChat if OPENAI_API_KEY is set)

Compatibility:
- Uses the same embedding model as your ingestion script by default.
- Works with the disk-backed Chroma DB created at ./chroma_db and collection "medical_knowledge".

Run:
    python rag_orchestrator.py --query "What are common migraine treatments?"

Notes:
- This file performs no web calls. LLM usage is optional and pluggable.
- For OpenAI, set OPENAI_API_KEY and OPENAI_MODEL (e.g., gpt-4o-mini).
"""

import os
import re
import time
import json
import math
import argparse
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional, Tuple, Protocol, Iterable, Set

import chromadb
from chromadb.config import Settings  # noqa: F401  # for possible extensions
from sentence_transformers import SentenceTransformer
from concurrent.futures import ThreadPoolExecutor, as_completed

# Load local .env early so environment variables (like OPENAI_API_KEY) are available
# to the module-level configuration below. We prefer python-dotenv when available
# but provide a small fallback parser so this works without extra deps.
def _load_local_dotenv() -> None:
    try:
        from dotenv import load_dotenv  # type: ignore
        # load .env from the project directory next to this file
        load_dotenv(os.path.join(os.path.dirname(__file__), ".env"))
        return
    except Exception:
        # simple fallback: parse KEY=VALUE lines (ignores export/complex shell)
        env_path = os.path.join(os.path.dirname(__file__), ".env")
        if os.path.exists(env_path):
            try:
                with open(env_path, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line or line.startswith("#"):
                            continue
                        if "=" in line:
                            k, v = line.split("=", 1)
                            k = k.strip()
                            v = v.strip()
                            # strip surrounding quotes if present
                            if (v.startswith('"') and v.endswith('"')) or (v.startswith("'") and v.endswith("'")):
                                v = v[1:-1]
                            # remove accidental leading spaces after '='
                            v = v.lstrip()
                            os.environ.setdefault(k, v)
            except Exception:
                # If anything goes wrong, silently continue and rely on existing env
                pass


_load_local_dotenv()

# ----------------------------
# CONFIG (edit as needed)
# ----------------------------

CHROMA_DB_DIR = os.environ.get("CHROMA_DB_DIR", "./chroma_db")
# If None, iterate over all collections in the DB.
# If you want to limit, set to a comma-separated list via env: CHROMA_COLLECTIONS="medical_knowledge,other"
COLLECTION_WHITELIST = os.environ.get("CHROMA_COLLECTIONS")
if COLLECTION_WHITELIST:
    COLLECTION_WHITELIST = [c.strip() for c in COLLECTION_WHITELIST.split(",") if c.strip()]

EMBEDDING_MODEL_NAME = os.environ.get(
    "EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2"
)
 

# LLM config (optional; will fall back to heuristic LLM if not available)
OPENAI_MODEL = os.environ.get("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_TEMPERATURE = float(os.environ.get("OPENAI_TEMPERATURE", "0.2"))

# Retrieval & thresholds
K_HEAD = int(os.environ.get("K_HEAD", "8"))          # quick head search for budgeting
K_RECALL = int(os.environ.get("K_RECALL", "200"))    # broad search per agent iteration (more permissive)
BAND_MAX = int(os.environ.get("BAND_MAX", "120"))    # cap on metadata-vetted candidates per iteration (more permissive)

X0 = float(os.environ.get("X0", "0.68"))             # initial strong threshold (more permissive)
Y0 = float(os.environ.get("Y0", "0.50"))             # initial band lower bound (more permissive, <= X0)
T_META0 = float(os.environ.get("T_META0", "0.35"))   # metadata relevance threshold in [0,1]

AGENT_MAX_ITERS = int(os.environ.get("AGENT_MAX_ITERS", "3"))
BASE_BUDGET_MS = int(os.environ.get("BASE_BUDGET_MS", "2500"))
MAX_BUDGET_MS = int(os.environ.get("MAX_BUDGET_MS", "12000"))
MIN_BUDGET_MS = int(os.environ.get("MIN_BUDGET_MS", "2000"))

MAX_WORKERS = int(os.environ.get("MAX_WORKERS", "4"))


def _score_from_collection_metadata(query: str, name: str, meta: Optional[Dict[str, Any]]) -> float:
    q = set(re.findall(r"[a-z0-9]+", query.lower()))
    pool: Set[str] = set(re.findall(r"[a-z0-9]+", name.lower()))
    if isinstance(meta, dict):
        t = meta.get("table")
        if t:
            pool.update(re.findall(r"[a-z0-9]+", str(t).lower()))
        fields = meta.get("fields")
        if isinstance(fields, dict):
            for k, v in fields.items():
                pool.update(re.findall(r"[a-z0-9]+", str(k).lower()))
                pool.update(re.findall(r"[a-z0-9]+", str(v).lower()))
    if not q or not pool:
        return 0.0
    inter = len(q.intersection(pool))
    return float(inter / max(1, len(q)))

# ----------------------------
# Embeddings provider (pluggable)
# ----------------------------

class EmbeddingsProvider(Protocol):
    def encode(self, texts: List[str]) -> List[List[float]]:
        ...

class SentenceTransformerEmbeddings:
    """Default embeddings provider using Sentence-Transformers."""
    def __init__(self, model_name: str = EMBEDDING_MODEL_NAME) -> None:
        self.model_name = model_name
        self.model = SentenceTransformer(model_name)

    def encode(self, texts: List[str]) -> List[List[float]]:
        # Keep parity with ingestion (no normalization flags)
        vecs = self.model.encode(texts, show_progress_bar=False)
        # Ensure list of lists
        return [v.tolist() if hasattr(v, "tolist") else list(v) for v in vecs]

# ----------------------------
# LLM provider (pluggable)
# ----------------------------

class LLMProvider(Protocol):
    """Abstract LLM provider interface."""
    def score_metadata(self, query: str, metadata: Dict[str, Any]) -> float:
        """Return relevance in [0,1] reading only metadata fields. Should be fast & cheap."""

    def map_summarize(self, query: str, doc_text: str, metadata: Dict[str, Any], citation_idx: int) -> str:
        """Return 1–2 sentence note that ends with [CITATION:{idx}]."""

    def reduce_summarize(self, query: str, notes_with_citations: List[str]) -> str:
        """Merge notes into a verbose, deduped summary with retained [CITATION:x] markers."""

    def orchestrator_reduce(self, query: str, agent_reports: List[Tuple[str, str]]) -> str:
        """Merge multiple agent summaries into a single coherent answer with citations kept."""
    def generate_chat_reply(self, query: str, final_answer: str, links: List[str]) -> str:
        """Produce a conversational, user-facing reply (may include links)."""

def _naive_overlap_score(query: str, meta: Dict[str, Any]) -> float:
    """Heuristic overlap between query terms and short metadata fields."""
    q = set(re.findall(r"[a-z0-9]+", query.lower()))
    fields = []
    for k in ("title", "disease_name", "section", "table"):
        v = meta.get(k)
        if v:
            fields.append(str(v))
    joined = " ".join(fields).lower()
    m = set(re.findall(r"[a-z0-9]+", joined))
    if not q or not m:
        return 0.0
    inter = len(q.intersection(m))
    score = inter / max(1, len(q))
    return float(max(0.0, min(1.0, score)))

class LocalHeuristicLLM:
    """
    Default, dependency-free LLM fallback.
    - Metadata scoring: token overlap heuristic.
    - Map summarize: extract salient lines from the doc text.
    - Reduce summarize: concatenates & deduplicates.
    - Orchestrator reduce: merges agent summaries with light dedupe.
    """

    def score_metadata(self, query: str, metadata: Dict[str, Any]) -> float:
        return _naive_overlap_score(query, metadata)

    def _best_lines(self, text: str, n: int = 2) -> List[str]:
        text = text.strip()
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if not lines:
            return []
        # Prefer lines under 220 chars and with medical keywords.
        keywords = ("symptom", "cause", "treat", "diagnos", "risk", "complication", "prevention", "dose", "indication")
        scored = []
        for ln in lines:
            base = 1.0 if len(ln) <= 220 else max(0.2, 220/ max(221, len(ln)))
            if any(kw in ln.lower() for kw in keywords):
                base += 0.3
            scored.append((base, ln))
        scored.sort(key=lambda x: x[0], reverse=True)
        return [ln for _, ln in scored[:n]]

    def map_summarize(self, query: str, doc_text: str, metadata: Dict[str, Any], citation_idx: int) -> str:
        title = metadata.get("title") or metadata.get("disease_name") or metadata.get("section") or ""
        header = f"{title}: " if title else ""
        lines = self._best_lines(doc_text, n=2)
        if not lines:
            snippet = (doc_text[:200] + "...") if len(doc_text) > 200 else doc_text
            lines = [snippet]
        body = " ".join(lines)
        # If metadata contains a URL, mention it briefly so the orchestrator can surface links.
        url = metadata.get("url") or metadata.get("source_url") or metadata.get("main_url") or metadata.get("uri")
        if url:
            # Keep the citation marker at the end
            return f"{header}{body} (see: {url}) [CITATION:{citation_idx}]"
        return f"{header}{body} [CITATION:{citation_idx}]"

    def generate_chat_reply(self, query: str, final_answer: str, links: List[str]) -> str:
        """Create a short conversational reply from the final merged answer and links.
        This is a lightweight fallback used when no external LLM is configured.
        """
        # Keep it short: 2-3 sentences plus links
        # Use the final_answer as the source of truth; extract first 2 sentences.
        parts = re.split(r'(?<=[\.\?!])\s+', final_answer.strip())
        summary = " ".join(parts[:2]).strip() if parts else final_answer.strip()
        if not summary:
            summary = final_answer.strip()
        out_lines = ["Hi — here’s a quick summary:", summary]
        if links:
            out_lines.append("\nUseful links:")
            for u in links:
                out_lines.append(f"- {u}")
        out_lines.append("\nWant me to expand on any point or show more sources?")
        return "\n".join(out_lines)

    def reduce_summarize(self, query: str, notes_with_citations: List[str]) -> str:
        # Simple dedupe by content digest
        seen: Set[str] = set()
        pieces: List[str] = []
        for note in notes_with_citations:
            key = re.sub(r"\[CITATION:[^\]]+\]", "", note).strip().lower()
            if key in seen:
                continue
            seen.add(key)
            pieces.append(note)
        # Group sentences and keep citations
        return " ".join(pieces)

    def orchestrator_reduce(self, query: str, agent_reports: List[Tuple[str, str]]) -> str:
        # agent_reports: List[(collection_name, summary_text)]
        # Lightly merge by concatenation with headings.
        blocks = []
        for coll, text in agent_reports:
            if text.strip():
                blocks.append(f"## {coll}\n{text.strip()}")
        return "\n\n".join(blocks)

class OpenAIChatLLM:
    """
    Optional OpenAI LLM provider.
    Requires: pip install openai  (either legacy or >= 1.0)
    Env vars: OPENAI_API_KEY, OPENAI_MODEL
    """
    def __init__(self, model: str = OPENAI_MODEL, temperature: float = OPENAI_TEMPERATURE):
        self.model = model
        self.temperature = temperature
        self._mode = None  # "v1", "legacy"
        self._client = None
        self._setup()

    def _setup(self) -> None:
        try:
            # New SDK style (>=1.0)
            from openai import OpenAI  # type: ignore
            self._client = OpenAI()
            self._mode = "v1"
        except Exception:
            try:
                # Legacy SDK
                import openai  # type: ignore
                self._client = openai
                self._mode = "legacy"
            except Exception:
                raise RuntimeError("OpenAI SDK not installed. Install `openai` or use the LocalHeuristicLLM.")

    def _chat(self, system_prompt: str, user_prompt: str) -> str:
        if self._mode == "v1":
            resp = self._client.chat.completions.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return resp.choices[0].message.content or ""
        else:
            # legacy
            self._client.api_key = os.environ.get("OPENAI_API_KEY")
            resp = self._client.ChatCompletion.create(
                model=self.model,
                temperature=self.temperature,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt},
                ],
            )
            return resp["choices"][0]["message"]["content"]

    def score_metadata(self, query: str, metadata: Dict[str, Any]) -> float:
        sys = "You are a strict metadata relevance scorer. Output ONLY a number in [0,1]."
        user = f"""Query: {query}
Metadata (short JSON): {json.dumps(metadata, ensure_ascii=False)}
How relevant is this metadata to the query? 1 = highly relevant, 0 = not relevant.
Return only a number in [0,1]."""
        txt = self._chat(sys, user).strip()
        try:
            # extract the first floating number
            m = re.search(r"\d*\.?\d+", txt)
            if m:
                val = float(m.group(0))
                return max(0.0, min(1.0, val))
        except Exception:
            pass
        return _naive_overlap_score(query, metadata)

    def map_summarize(self, query: str, doc_text: str, metadata: Dict[str, Any], citation_idx: int) -> str:
        sys = "You write concise, accurate notes. Keep 1–2 sentences. End with [CITATION:{idx}]."
        sys = sys.format(idx=citation_idx)
        user = f"""Query: {query}

Metadata:
{json.dumps(metadata, ensure_ascii=False)}

Doc:
\"\"\"
{doc_text}
\"\"\"

Task: Extract only facts that directly answer the query. 1–2 sentences. End with [CITATION:{citation_idx}].
"""
        out = self._chat(sys, user).strip()
        # Guarantee a citation tag
        if f"[CITATION:{citation_idx}]" not in out:
            out = out.rstrip(". ") + f" [CITATION:{citation_idx}]"
        return out

    def reduce_summarize(self, query: str, notes_with_citations: List[str]) -> str:
        sys = "You merge evidence notes into a verbose, accurate summary. Keep all [CITATION:x] markers."
        user = f"""Query: {query}
Evidence notes:
{chr(10).join(f"- {n}" for n in notes_with_citations)}

Task: Merge into a single coherent paragraph. Deduplicate, surface consensus vs. disagreements.
Keep the [CITATION:x] markers in place.
"""
        return self._chat(sys, user).strip()

    def generate_chat_reply(self, query: str, final_answer: str, links: List[str]) -> str:
        """Use the OpenAI chat model to produce a conversational reply that includes the provided links.
        Falls back to returning the final_answer if the model call fails.
        """
        sys = "You are a helpful assistant that writes concise, conversational replies for end users."
        user = f"""Query: {query}

Final merged answer:
{final_answer}

Links:
{chr(10).join(links) if links else '(none)'}

Task: Produce a short (2-3 sentence) conversational reply suitable for a chat UI, and append the links as a bulleted list. Keep it friendly and offer to expand.
"""
        try:
            out = self._chat(sys, user).strip()
            return out
        except Exception:
            return final_answer

    def orchestrator_reduce(self, query: str, agent_reports: List[Tuple[str, str]]) -> str:
        sys = "You merge multiple agent summaries into a single, coherent, comprehensive answer. Preserve [CITATION:x] markers."
        joined = "\n\n".join([f"### {name}\n{txt}" for name, txt in agent_reports])
        user = f"""Query: {query}
Agent summaries:
{joined}

Task: Produce one comprehensive answer. Avoid repetition, reconcile overlaps, and keep [CITATION:x] markers intact.
"""
        return self._chat(sys, user).strip()

def build_llm_provider() -> LLMProvider:
    api_key = os.environ.get("OPENAI_API_KEY")
    if api_key:
        try:
            return OpenAIChatLLM()
        except Exception as e:
            print(f"[LLM] Falling back to LocalHeuristicLLM ({e})")
    return LocalHeuristicLLM()

# ----------------------------
# Data structures
# ----------------------------

@dataclass
class Doc:
    id: str
    text: str
    meta: Dict[str, Any]
    s_embed: float

@dataclass
class AgentOutput:
    collection: str
    summary_text: str
    citations: List[Dict[str, Any]]
    used_docs: List[Doc]
    metrics: Dict[str, Any]
    confidence: float

@dataclass
class Thresholds:
    X: float
    Y: float
    T_meta: float

# ----------------------------
# Chroma utilities
# ----------------------------

def ann_search(collection, q_vec: List[float], k: int) -> List[Doc]:
    """
    Chroma ANN query returning Doc objects sorted by similarity descending.
    Assumes collection was built with cosine space: s = 1 - distance.
    """
    res = collection.query(
        query_embeddings=[q_vec],
        n_results=k,
        # "ids" is not accepted in some Chroma versions for the include list;
        # omitting it is safe because the client still returns an 'ids' key.
        include=["metadatas", "documents", "distances"],
    )
    docs: List[Doc] = []
    if not res or not res.get("ids"):
        return docs

    ids        = res["ids"][0]
    docs_text  = res.get("documents", [[]])[0] or []
    metas      = res.get("metadatas", [[]])[0] or []
    distances  = res.get("distances", [[]])[0] or []

    for i, _id in enumerate(ids):
        dist = distances[i] if i < len(distances) else None
        # cosine similarity from Chroma distance under hnsw:space=cosine
        sim = float(1.0 - float(dist)) if dist is not None else 0.0
        text = docs_text[i] if i < len(docs_text) else ""
        meta = metas[i] if i < len(metas) else {}
        docs.append(Doc(id=_id, text=text, meta=meta, s_embed=sim))

    # sort by similarity descending (defensive)
    docs.sort(key=lambda d: d.s_embed, reverse=True)
    return docs

# ----------------------------
# Scoring & heuristics
# ----------------------------

def mean(xs: Iterable[float]) -> float:
    xs = list(xs)
    return (sum(xs) / len(xs)) if xs else 0.0

def clamp(lo: float, hi: float, x: float) -> float:
    return max(lo, min(hi, x))

def now_ms() -> int:
    return int(time.time() * 1000)

def coverage_score(docs: List[Doc]) -> float:
    sections = {d.meta.get("section") for d in docs if d.meta.get("section")}
    titles = {
        d.meta.get("title") or d.meta.get("disease_name")
        for d in docs
        if d.meta.get("title") or d.meta.get("disease_name")
    }
    # saturating transform to [0,1]
    cov = 0.5 * (1 - math.exp(-len(sections) / 3.0)) + 0.5 * (1 - math.exp(-len(titles) / 5.0))
    return float(cov)

def novelty_score(cur_ids: Set[str], prev_ids: Set[str]) -> float:
    if not cur_ids:
        return 0.0
    return float(len(cur_ids - prev_ids) / max(1, len(cur_ids)))

def dedupe_docs(docs: List[Doc]) -> List[Doc]:
    seen_ids: Set[str] = set()
    seen_keys: Set[Tuple[Any, ...]] = set()
    unique: List[Doc] = []
    for d in docs:
        key = (
            d.meta.get("table"),
            d.meta.get("row_index"),
            d.meta.get("title") or d.meta.get("disease_name"),
            d.meta.get("section"),
        )
        if d.id in seen_ids or key in seen_keys:
            continue
        seen_ids.add(d.id)
        seen_keys.add(key)
        unique.append(d)
    return unique

# ----------------------------
# Agent iteration
# ----------------------------

def summarize_verbose(llm: LLMProvider, query: str, docs: List[Doc]) -> Tuple[str, List[Dict[str, Any]], float]:
    notes: List[str] = []
    citations: List[Dict[str, Any]] = []
    for idx, d in enumerate(docs, start=1):
        note = llm.map_summarize(query, d.text, d.meta, citation_idx=idx)
        notes.append(note)
        citations.append({
            "collection": d.meta.get("collection") or d.meta.get("table") or "",
            "doc_id": d.id,
            "section": d.meta.get("section"),
            "title": d.meta.get("title") or d.meta.get("disease_name"),
            # prefer common url fields that might be present in metadata
            "url": (d.meta.get("url") or d.meta.get("source_url") or d.meta.get("main_url") or d.meta.get("uri") or None),
            "s_embed": d.s_embed,
        })
    merged = llm.reduce_summarize(query, notes) if notes else ""
    avg_sim = mean(d.s_embed for d in docs) if docs else 0.0
    confidence = min(1.0, 0.4 + 0.6 * min(1.0, (len(docs) / 10.0)) * avg_sim)
    return merged, citations, confidence

def run_agent_once(
    collection,
    collection_name: str,
    query_text: str,
    q_vec: List[float],
    thr: Thresholds,
    llm: LLMProvider,
    k_head: int = K_HEAD,
    k_recall: int = K_RECALL,
    band_max: int = BAND_MAX,
    time_limit_ms: int = 4000,
) -> AgentOutput:
    t0 = now_ms()

    # quick head
    head = ann_search(collection, q_vec, k_head)
    head_top = head[0].s_embed if head else 0.0

    # full recall
    candidates = ann_search(collection, q_vec, k_recall)
    strong = [d for d in candidates if d.s_embed >= thr.X]
    band_raw = [d for d in candidates if (thr.Y <= d.s_embed < thr.X)]
    band_raw = band_raw[:band_max]

    # metadata vetting
    band_vetted: List[Doc] = []
    for d in band_raw:
        if now_ms() - t0 > time_limit_ms * 0.6:
            break
        s_meta = llm.score_metadata(query_text, d.meta)
        if s_meta >= thr.T_meta:
            band_vetted.append(d)

    selected = dedupe_docs(strong + band_vetted)

    # summarize
    summary, citations, conf = summarize_verbose(llm, query_text, selected)

    metrics = {
        "count": len(selected),
        "avg_sim": mean([d.s_embed for d in selected]) if selected else 0.0,
        "strong_share": (len([d for d in selected if d in strong]) / max(1, len(selected))) if selected else 0.0,
        "top_head_sim": head_top,
        "time_ms": now_ms() - t0,
    }

    # annotate collection in citations
    for c in citations:
        if not c.get("collection"):
            c["collection"] = collection_name

    return AgentOutput(
        collection=collection_name,
        summary_text=summary,
        citations=citations,
        used_docs=selected,
        metrics=metrics,
        confidence=conf,
    )

def initial_thresholds() -> Thresholds:
    return Thresholds(X=X0, Y=Y0, T_meta=T_META0)

def estimate_agent_budget_ms(head_top: float, collection_size: int) -> int:
    base = BASE_BUDGET_MS
    bonus = int(4000 * clamp(0.0, 1.0, 0.5 * head_top + 0.5 * min(1.0, math.log1p(max(1, collection_size)) / 10.0)))
    return int(clamp(MIN_BUDGET_MS, MAX_BUDGET_MS, base + bonus))

def utility(output: AgentOutput, prev_output: Optional[AgentOutput]) -> float:
    cov = coverage_score(output.used_docs)
    evidence = 0.5 * output.metrics.get("avg_sim", 0.0) + 0.5 * output.metrics.get("strong_share", 0.0)
    prev_ids = {d.id for d in prev_output.used_docs} if prev_output else set()
    nov = novelty_score({d.id for d in output.used_docs}, prev_ids)
    return float(0.4 * cov + 0.45 * evidence + 0.15 * nov)

def thresholds_tweak(thr: Thresholds, out: AgentOutput, u_now: float, u_prev: Optional[float], elapsed_ratio: float = 0.0) -> Thresholds:
    X, Y, T = thr.X, thr.Y, thr.T_meta
    count = out.metrics.get("count", 0)
    avg_sim = out.metrics.get("avg_sim", 0.0)
    strong_share = out.metrics.get("strong_share", 0.0)
    delta_u = (u_now - (u_prev or 0.0))
    # Increase step size as time elapses toward the hard limit to ensure convergence
    base = 0.02
    step = base * (1.0 + 2.0 * max(0.0, min(1.0, elapsed_ratio)))

    if count == 0:
        # No docs selected: lower thresholds more aggressively over time
        Y = max(0.0, Y - 3 * step)
        X = max(Y + 0.01, X - 2 * step)
    elif count < 5 and avg_sim >= 0.75:
        Y = max(0.0, Y - step)
    elif count > 40 and avg_sim < 0.70:
        X = min(0.99, X + step)
        Y = min(X, Y + 0.5 * step)
    elif strong_share < 0.4 and avg_sim < 0.72:
        X = min(0.99, X + step)
        Y = min(X, Y + step)
    elif delta_u > 0:
        Y = max(0.0, Y - 0.5 * step)
    else:
        X = min(0.99, X + 0.5 * step)

    Y = min(Y, X)
    return Thresholds(X=X, Y=Y, T_meta=T)

def agent_loop(collection, collection_name: str, query_text: str, q_vec: List[float], llm: LLMProvider) -> AgentOutput:
    thr = initial_thresholds()
    # budget via quick head
    head = ann_search(collection, q_vec, k=5)
    head_top = head[0].s_embed if head else 0.0
    try:
        csize = collection.count()
    except Exception:
        csize = 0
    budget = estimate_agent_budget_ms(head_top, csize)
    per_iter_cap = max(1, budget // AGENT_MAX_ITERS)

    best_out: Optional[AgentOutput] = None
    prev_out: Optional[AgentOutput] = None
    u_prev: Optional[float] = None
    elapsed = 0
    t_start = now_ms()
    # Determine hard time limit per agent safely even if the global is missing
    try:
        hard_limit_ms = int(os.environ.get("AGENT_HARD_TIME_LIMIT_MS", str(AGENT_HARD_TIME_LIMIT_MS)))
    except NameError:
        hard_limit_ms = int(os.environ.get("AGENT_HARD_TIME_LIMIT_MS", "12000"))

    for i in range(AGENT_MAX_ITERS):
        if now_ms() - t_start >= hard_limit_ms:
            print(f"[Agent:{collection_name}] hard_time_limit hit at ~{now_ms() - t_start} ms; stopping")
            break
        print(
            f"[Agent:{collection_name}] iter={i+1} thr_before X={thr.X:.3f} Y={thr.Y:.3f} T_meta={thr.T_meta:.2f}"
        )
        out = run_agent_once(
            collection=collection,
            collection_name=collection_name,
            query_text=query_text,
            q_vec=q_vec,
            thr=thr,
            llm=llm,
            time_limit_ms=per_iter_cap,
        )
        u_now = utility(out, prev_out)
        print(
            f"[Agent:{collection_name}] iter={i+1} metrics count={out.metrics['count']} avg_sim={out.metrics['avg_sim']:.3f} "
            f"strong_share={out.metrics['strong_share']:.2f} top_head_sim={out.metrics['top_head_sim']:.3f} time_ms={out.metrics['time_ms']} "
            f"utility={u_now:.3f} conf={out.confidence:.2f}"
        )

        if best_out is None or u_now > utility(best_out, None):
            best_out = out

        # stopping rules
        good_coverage = out.metrics["count"] >= 8 and out.metrics["avg_sim"] >= 0.72
        high_conf = out.confidence >= 0.7
        diminishing = (u_prev is not None and (u_now - u_prev) < 0.03)

        if good_coverage and high_conf:
            break
        if diminishing and elapsed >= (2 * per_iter_cap):
            break
        if elapsed + out.metrics["time_ms"] > budget:
            break

        # prepare next iteration (more aggressive lowering as time elapses)
        elapsed_global = now_ms() - t_start
        elapsed_ratio = float(min(1.0, elapsed_global / max(1, hard_limit_ms)))
        thr = thresholds_tweak(thr, out, u_now, u_prev, elapsed_ratio=elapsed_ratio)
        print(
            f"[Agent:{collection_name}] iter={i+1} thr_after  X={thr.X:.3f} Y={thr.Y:.3f} T_meta={thr.T_meta:.2f} (elapsed={elapsed_global}ms, ratio={elapsed_ratio:.2f})"
        )
        prev_out = out
        u_prev = u_now
        elapsed += out.metrics["time_ms"]

    assert best_out is not None
    return best_out

# ----------------------------
# Citation plumbing
# ----------------------------

def assign_global_citations(agent_outputs: List[AgentOutput]) -> Tuple[Dict[Tuple[str, str], str], List[Dict[str, Any]]]:
    """
    Build a stable mapping from (collection, doc_id) -> label like 'A1', 'A2', ...
    Return (mapping, ordered_bibliography_list)
    """
    mapping: Dict[Tuple[str, str], str] = {}
    bibliography: List[Dict[str, Any]] = []
    idx = 1
    for out in agent_outputs:
        for c in out.citations:
            key = (out.collection, c.get("doc_id", ""))
            if key in mapping:
                continue
            label = f"A{idx}"
            mapping[key] = label
            bib = {
                "label": label,
                "collection": out.collection,
                "doc_id": c.get("doc_id"),
                "title": c.get("title"),
                "section": c.get("section"),
                "url": c.get("url"),
                "s_embed": c.get("s_embed"),
            }
            bibliography.append(bib)
            idx += 1
    return mapping, bibliography

def relabel_agent_summary(summary_text: str, citations: List[Dict[str, Any]], collection_name: str,
                          label_map: Dict[Tuple[str, str], str]) -> str:
    """
    Replace local [CITATION:i] markers with global labels [A#].
    The i-th marker corresponds to citations[i-1] doc.
    """
    # Build local index -> global label
    local_to_global: Dict[int, str] = {}
    for i, c in enumerate(citations, start=1):
        key = (collection_name, c.get("doc_id", ""))
        if key in label_map:
            local_to_global[i] = label_map[key]

    def _replace(match: re.Match) -> str:
        nums = match.group(1)
        parts = re.split(r"\s*,\s*", nums.strip())
        labels = []
        for p in parts:
            try:
                idx = int(p)
                labels.append(local_to_global.get(idx, f"?{idx}"))
            except Exception:
                labels.append(p)
        # dedupe order-preserving
        seen: Set[str] = set()
        labels = [x for x in labels if not (x in seen or seen.add(x))]
        return "[" + ", ".join(labels) + "]"

    # Accept markers like [CITATION:3] or [CITATION:1,7]
    out = re.sub(r"\[CITATION:([0-9,\s]+)\]", _replace, summary_text)
    return out

def format_bibliography(biblio: List[Dict[str, Any]]) -> str:
    lines = []
    for item in biblio:
        label = item.get("label")
        title = item.get("title") or "(untitled)"
        sec = item.get("section")
        sec_str = f" — {sec}" if sec else ""
        url = item.get("url")
        url_str = f" — {url}" if url else ""
        doc_id = item.get("doc_id")
        lines.append(f"{label}: {title}{sec_str} — {item.get('collection')} ({doc_id}){url_str}")
    return "\n".join(lines)

# ----------------------------
# Orchestrator
# ----------------------------

def orchestrate(query_text: str,
                client: chromadb.PersistentClient,
                embedder: EmbeddingsProvider,
                llm: LLMProvider,
                collections_filter: Optional[List[str]] = None,
                max_workers: int = MAX_WORKERS) -> Dict[str, Any]:

    # Enumerate collections
    all_collections = client.list_collections()
    named = [(c.name, c) for c in all_collections]
    if collections_filter:
        wanted = set(collections_filter)
        named = [(n, c) for (n, c) in named if n in wanted]

    if not named:
        raise RuntimeError("No Chroma collections found. Did you create 'medical_knowledge' already?")

    try:
        scored = []
        for n, c in named:
            try:
                meta = getattr(c, "metadata", None)
            except Exception:
                meta = None
            s = _score_from_collection_metadata(query_text, n, meta)
            scored.append((s, n, c))
        filtered = [(n, c) for (s, n, c) in scored if s > 0.0]
        if filtered:
            named = filtered
    except Exception:
        pass

    # Embed query
    q_vec = embedder.encode([query_text])[0]

    # Run agents in parallel
    outputs: List[AgentOutput] = []
    with ThreadPoolExecutor(max_workers=min(max_workers, len(named))) as pool:
        futures = {pool.submit(agent_loop, c, n, query_text, q_vec, llm): n for (n, c) in named}
        for fut in as_completed(futures):
            name = futures[fut]
            try:
                out = fut.result()
                outputs.append(out)
            except Exception as e:
                print(f"[Agent:{name}] error: {e}")

    if not outputs:
        raise RuntimeError("All agents failed or returned no output.")

    # Score & order agents by utility
    scored = sorted(outputs, key=lambda o: utility(o, None), reverse=True)

    # Assign global citations
    label_map, bibliography = assign_global_citations(scored)

    # Relabel agent summaries to global markers and collect for final reduce
    relabeled_reports: List[Tuple[str, str]] = []
    for out in scored:
        relabeled = relabel_agent_summary(out.summary_text, out.citations, out.collection, label_map)
        relabeled_reports.append((out.collection, relabeled))

    # Final merge
    final_answer = llm.orchestrator_reduce(query_text, relabeled_reports)
    bib_text = format_bibliography(bibliography)

    # collect unique non-empty links from the bibliography (preserve order)
    links: List[str] = []
    seen_links: Set[str] = set()
    for item in bibliography:
        url = item.get("url")
        if url and url not in seen_links:
            links.append(url)
            seen_links.add(url)

    return {
        "answer": final_answer,
        "citations": bib_text,
        "links": links,
        "per_agent": [
            {
                "collection": o.collection,
                "metrics": o.metrics,
                "confidence": o.confidence,
                "docs_used": len(o.used_docs),
            }
            for o in scored
        ],
        "collections_considered": [n for n, _ in named],
    }

# ----------------------------
# CLI
# ----------------------------

def main() -> None:
    parser = argparse.ArgumentParser(description="Agentic RAG Orchestrator over Chroma collections")
    parser.add_argument("--query", required=True, help="User query to answer")
    parser.add_argument("--collections", nargs="*", default=COLLECTION_WHITELIST,
                        help="Optional list of collection names to restrict to")
    parser.add_argument("--json", action="store_true", help="Print raw JSON result")
    args = parser.parse_args()

    # Embeddings
    embedder = SentenceTransformerEmbeddings(EMBEDDING_MODEL_NAME)
    # LLM
    llm = build_llm_provider()

    # Chroma client
    client = chromadb.PersistentClient(path=CHROMA_DB_DIR)

    result = orchestrate(
        query_text=args.query,
        client=client,
        embedder=embedder,
        llm=llm,
        collections_filter=args.collections,
    )

    if args.json:
        print(json.dumps(result, ensure_ascii=False, indent=2))
    else:
        # Prefer letting the configured LLM produce the final conversational reply.
        try:
            chat_reply = llm.generate_chat_reply(args.query, result.get("answer", ""), result.get("links", []))
        except Exception:
            # Fallback: build a concise reply from the merged answer and links (previous behavior)
            full = result.get("answer", "").strip()
            parts = re.split(r'(?<=[\.\?!])\s+', full)
            concise = " ".join(parts[:2]).strip() if parts else full
            if not concise:
                concise = full
            links = result.get("links", [])
            lines = ["Here's a quick answer:", "", concise]
            if links:
                lines.append("")
                lines.append("You can read more at the following links:")
                for url in links:
                    lines.append(f"- {url}")
            else:
                lines.append("\nSources:")
                lines.append(result.get("citations", ""))
            lines.append("")
            lines.append("If you'd like, I can expand on any of these points or show more sources.")
            chat_reply = "\n".join(lines)

        print("\n================== ANSWER ==================\n")
        print(chat_reply)
        print("\n----------------- METRICS ------------------\n")
        for entry in result["per_agent"]:
            print(f"- {entry['collection']}: "
                  f"docs_used={entry['docs_used']}, "
                  f"avg_sim={entry['metrics'].get('avg_sim'):.3f}, "
                  f"strong_share={entry['metrics'].get('strong_share'):.2f}, "
                  f"time_ms={entry['metrics'].get('time_ms')},"
                  f" conf={entry['confidence']:.2f}")
        print("\nCollections considered:", ", ".join(result["collections_considered"]))

if __name__ == "__main__":
    main()
