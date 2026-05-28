"""
Vision Agent - Multimodal Medical Image Analysis

Performs "Neuro-Symbolic" analysis by combining:
1. Vision: Analyzes the image using LLaVA/Gemini (vision_tool)
2. Visual Search: Finds similar historical scans (BiomedCLIP/ChromaDB)
3. Semantic Search: Retrieves medical guidelines (text RAG) with cross-encoder reranking

Anti-Hallucination Measures:
- No MockTool fallback: vision_tool import failure is fatal (prevents fake findings)
- Visual-RAG similarity threshold: only show cases above 70% similarity
- Text-RAG uses cross-encoder reranking to filter irrelevant guidelines
- Search query extracted conservatively from structured vision output
"""

import os
import sys
import json
import hashlib
import importlib.util
import chromadb
from collections import OrderedDict
from langchain_core.tools import tool

# Add project root to path for imports
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.runtime_config import CHROMA_DB_DIR, ENABLE_VISUAL_RAG

# --- IMPORTS FROM EXISTING TOOLS ---

# 1. The "Eyes" (Hybrid Vision Tool) — NO FALLBACK, must be available
try:
    from src.vision_tool import analyze_medical_image
except ImportError:
    try:
        from vision_tool import analyze_medical_image
    except ImportError:
        # CRITICAL: No MockTool. If vision_tool is unavailable, analysis should fail
        # rather than producing fake "consolidation" findings that propagate downstream.
        analyze_medical_image = None
        print("❌ CRITICAL: vision_tool not found. Vision analysis will be unavailable.")

# 2. The "Visual Memory" (BiomedCLIP Search)
if ENABLE_VISUAL_RAG and importlib.util.find_spec("open_clip"):
    try:
        from ingestion.ingest_images import search_similar_images, search_by_text
    except ImportError:
        print("⚠️ Warning: ingest_images not found. Visual search disabled.")
        search_similar_images = None
        search_by_text = None
else:
    search_similar_images = None
    search_by_text = None

# 3. Cross-Encoder Reranker for Text-RAG
try:
    from src.reranker import rerank_documents
except ImportError:
    try:
        from reranker import rerank_documents
    except ImportError:
        print("⚠️ Warning: reranker not found. Text-RAG will skip reranking.")
        rerank_documents = None

# --- CONFIGURATION ---
CHROMA_PATH = CHROMA_DB_DIR
TEXT_COLLECTION_NAME = "diseases"  # From Phase 2 text ingestion
VISUAL_SIMILARITY_THRESHOLD = 0.70  # Only show cases above 70% similarity
TEXT_RAG_RERANK_TOP_K = 3           # Keep top 3 after reranking

# Flag to skip text-RAG when called from the brain (which does its own broader vector search)
# This prevents duplicate ChromaDB queries. Set to True by trustmed_brain before calling.
_skip_text_rag = False

# =============================================================================
# Vision Result Cache (SHA-256 image hash → analysis result)
# =============================================================================

_VISION_CACHE_MAX_SIZE = 50  # Max cached image results (~5KB each = ~250KB)
_vision_cache = OrderedDict()  # {sha256_hex: result_string}
_cache_stats = {"hits": 0, "misses": 0}


def _compute_image_hash(image_path: str) -> str:
    """Compute SHA-256 hash of an image file for cache lookup."""
    sha256 = hashlib.sha256()
    with open(image_path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            sha256.update(chunk)
    return sha256.hexdigest()


def get_vision_cache_stats() -> dict:
    """Return cache hit/miss stats and current size."""
    total = _cache_stats["hits"] + _cache_stats["misses"]
    return {
        "hits": _cache_stats["hits"],
        "misses": _cache_stats["misses"],
        "hit_rate": f"{_cache_stats['hits'] / total:.0%}" if total > 0 else "N/A",
        "cached_images": len(_vision_cache),
        "max_size": _VISION_CACHE_MAX_SIZE,
    }


def clear_vision_cache():
    """Clear the vision result cache."""
    _vision_cache.clear()
    _cache_stats["hits"] = 0
    _cache_stats["misses"] = 0
    print("🗑️ Vision cache cleared.")

def set_skip_text_rag(skip: bool):
    """Allow the brain orchestrator to disable text-RAG to avoid duplicate retrieval."""
    global _skip_text_rag
    _skip_text_rag = skip


def get_text_retriever():
    """Connects to the text-based disease knowledge base."""
    try:
        client = chromadb.PersistentClient(path=CHROMA_PATH)
        collection = client.get_collection(name=TEXT_COLLECTION_NAME)
        return collection
    except Exception as e:
        print(f"⚠️ Text collection '{TEXT_COLLECTION_NAME}' not found: {e}")
        return None


# --- SEARCH QUERY EXTRACTION ---

def _extract_search_query(vision_output: str) -> str:
    """
    Extract a conservative search query from vision model output.

    Only uses HIGH-CONFIDENCE findings and modality/region for the search query.
    This prevents hallucinated findings from being used as RAG search seeds.

    Args:
        vision_output: Full output from analyze_medical_image

    Returns:
        Conservative search query string
    """
    query_parts = []

    # Try to parse structured JSON from the vision output
    try:
        # Find JSON-like content in the output
        # The structured output is between the header and the footer tags
        lines = vision_output.split('\n')
        # Look for modality and high-confidence findings
        for line in lines:
            stripped = line.strip()
            if stripped.startswith("Modality & Region:"):
                modality_region = stripped.replace("Modality & Region:", "").strip()
                query_parts.append(modality_region)
            elif stripped.startswith("[HIGH]"):
                finding = stripped.replace("[HIGH]", "").strip()
                query_parts.append(finding)
            elif stripped.startswith("Overall Impression:"):
                impression = stripped.replace("Overall Impression:", "").strip()
                query_parts.append(impression)
    except Exception:
        pass

    if query_parts:
        return " ".join(query_parts)[:300]

    # Fallback: if we couldn't parse structured output, use a truncated version
    # but strip emojis, decorators, and format markers
    clean_lines = []
    for line in vision_output.split('\n'):
        stripped = line.strip()
        if not stripped:
            continue
        # Skip decorative lines
        if stripped.startswith(('🔬', '===', '---', '[WARNING', '[UNSTRUCTURED')):
            continue
        if '[LOW]' in stripped:
            continue  # Skip uncertain findings for search
        clean_lines.append(stripped)

    fallback = " ".join(clean_lines)[:200]
    return fallback if fallback else "medical imaging pathology"


# --- CROSS-REFERENCE VALIDATION ---

# Condition name aliases for fuzzy matching between vision model output and MIMIC labels
_CONDITION_ALIASES = {
    "atelectasis": ["atelectasis", "atelectatic", "collapse"],
    "cardiomegaly": ["cardiomegaly", "enlarged heart", "cardiac enlargement"],
    "consolidation": ["consolidation", "consolidated"],
    "edema": ["edema", "oedema", "pulmonary edema", "fluid"],
    "enlarged cardiomediastinum": ["enlarged cardiomediastinum", "mediastinal widening", "widened mediastinum"],
    "fracture": ["fracture", "fractured", "broken"],
    "lung lesion": ["lung lesion", "lesion", "mass", "nodule", "tumor"],
    "lung opacity": ["lung opacity", "opacity", "opacification", "opacities", "haziness"],
    "no finding": ["no finding", "normal", "unremarkable", "no abnormality"],
    "pleural effusion": ["pleural effusion", "effusion", "fluid in pleural"],
    "pleural other": ["pleural other", "pleural thickening", "pleural calcification"],
    "pneumonia": ["pneumonia", "pneumonic", "infection", "infectious"],
    "pneumothorax": ["pneumothorax", "collapsed lung", "air in pleural"],
    "support devices": ["support devices", "lines", "tubes", "catheter", "pacemaker", "device"],
}

CROSS_REF_TOP_K = 10          # Number of similar images to check
CROSS_REF_THRESHOLD = 0.30    # 30% — finding must appear in ≥30% of similar images
CROSS_REF_MIN_SIMILARITY = 0.60  # Minimum similarity to count as a valid match


def _match_finding_to_condition(finding_text: str) -> list:
    """
    Match a free-text vision model finding to MIMIC-CXR condition names.
    Returns list of matched condition names (lowercase).
    """
    finding_lower = finding_text.lower()
    matches = []
    for condition, aliases in _CONDITION_ALIASES.items():
        for alias in aliases:
            if alias in finding_lower:
                matches.append(condition)
                break
    return matches


def _cross_reference_findings(vision_output: str, image_path: str) -> str:
    """
    Cross-reference vision model findings against ground-truth labels
    from similar MIMIC-CXR images in the Visual RAG database.

    For each HIGH finding from the vision model:
    - If ≥30% of similar labeled images share that condition → CORROBORATED
    - Otherwise → NOT CORROBORATED (possible hallucination)

    Also flags conditions that appear frequently in similar images
    but were NOT mentioned by the vision model (potential misses).

    Args:
        vision_output: The formatted vision model output
        image_path: Path to the query image

    Returns:
        Formatted cross-reference report string, or None if insufficient data
    """
    if not vision_output or not search_similar_images:
        return None

    # 1. Get similar labeled images from ChromaDB
    try:
        visual_results = search_similar_images(image_path, n_results=CROSS_REF_TOP_K)
    except Exception:
        return None

    if not visual_results or not visual_results.get("ids") or not visual_results["ids"][0]:
        return None

    # 2. Collect ground-truth labels from similar MIMIC-CXR images
    label_counts = {}  # condition → count
    mimic_matches = 0

    for metadata, distance in zip(
        visual_results["metadatas"][0],
        visual_results["distances"][0]
    ):
        similarity = 1 - distance
        if similarity < CROSS_REF_MIN_SIMILARITY:
            continue

        source = metadata.get("source", "")
        labels_str = metadata.get("labels_list", metadata.get("label", ""))

        # Only count MIMIC-CXR images (with ground-truth labels)
        if source == "mimic-cxr-jpg" and labels_str:
            mimic_matches += 1
            for lbl in labels_str.split("|"):
                lbl = lbl.strip().lower()
                if lbl:
                    label_counts[lbl] = label_counts.get(lbl, 0) + 1

    # Need at least 3 MIMIC-CXR matches for meaningful cross-referencing
    if mimic_matches < 3:
        return f"   Insufficient MIMIC-CXR matches ({mimic_matches}/3 required) for cross-referencing."

    # 3. Extract HIGH findings from vision output
    high_findings = []
    for line in vision_output.split("\n"):
        stripped = line.strip()
        if stripped.startswith("[HIGH]"):
            finding = stripped.replace("[HIGH]", "").strip()
            high_findings.append(finding)

    if not high_findings:
        # No HIGH findings to validate
        lines = [f"   Based on {mimic_matches} similar MIMIC-CXR cases:"]
        if label_counts:
            lines.append("   Conditions in similar images:")
            for cond, cnt in sorted(label_counts.items(), key=lambda x: -x[1]):
                pct = cnt / mimic_matches * 100
                lines.append(f"     • {cond.title()}: {cnt}/{mimic_matches} ({pct:.0f}%)")
        return "\n".join(lines)

    # 4. Validate each HIGH finding
    lines = [f"   Cross-referencing against {mimic_matches} similar MIMIC-CXR cases:"]
    corroborated = []
    uncorroborated = []

    for finding in high_findings:
        matched_conditions = _match_finding_to_condition(finding)

        if not matched_conditions:
            # Can't map to a known condition — treat as uncertain
            lines.append(f"   ⚠  [HIGH] {finding}")
            lines.append(f"      → Cannot map to standard CXR condition — treat with caution")
            uncorroborated.append(finding)
            continue

        # Check if any matched condition appears in similar images
        best_match = None
        best_pct = 0
        for cond in matched_conditions:
            cnt = label_counts.get(cond, 0)
            pct = cnt / mimic_matches
            if pct > best_pct:
                best_pct = pct
                best_match = cond

        if best_pct >= CROSS_REF_THRESHOLD:
            cnt = label_counts.get(best_match, 0)
            lines.append(f"   ✅ [HIGH] {finding}")
            lines.append(f"      → CORROBORATED: {best_match.title()} in {cnt}/{mimic_matches} similar cases ({best_pct:.0%})")
            corroborated.append(finding)
        else:
            lines.append(f"   ⚠  [HIGH] {finding}")
            if best_match:
                cnt = label_counts.get(best_match, 0)
                lines.append(f"      → NOT CORROBORATED: {best_match.title()} in only {cnt}/{mimic_matches} cases ({best_pct:.0%}) — possible hallucination")
            else:
                lines.append(f"      → NOT CORROBORATED by similar cases — possible hallucination")
            uncorroborated.append(finding)

    # 5. Check for conditions in similar images NOT mentioned by vision model
    vision_text_lower = vision_output.lower()
    missed = []
    for cond, cnt in sorted(label_counts.items(), key=lambda x: -x[1]):
        pct = cnt / mimic_matches
        if pct >= 0.50:  # Present in ≥50% of similar cases
            # Check if vision model mentioned it
            aliases = _CONDITION_ALIASES.get(cond, [cond])
            mentioned = any(alias in vision_text_lower for alias in aliases)
            if not mentioned and cond != "support devices":
                missed.append((cond, cnt, pct))

    if missed:
        lines.append("\n   🔍 POTENTIALLY MISSED (frequent in similar cases but not reported):")
        for cond, cnt, pct in missed:
            lines.append(f"     • {cond.title()}: {cnt}/{mimic_matches} ({pct:.0%}) of similar cases")

    # 6. Summary
    lines.append("")
    total = len(corroborated) + len(uncorroborated)
    lines.append(f"   Summary: {len(corroborated)}/{total} findings corroborated by labeled database")
    if uncorroborated:
        lines.append(f"   ⚠ {len(uncorroborated)} finding(s) not supported — recommend clinical verification")

    return "\n".join(lines)


# --- THE AGENT ---

@tool
def analyze_and_retrieve_context(image_path: str) -> str:
    """
    Multimodal Analysis Agent:
    1. Analyzes image to identify pathology (Vision).
    2. Retrieves medical guidelines for that pathology (Text RAG).
    3. Finds visually similar past cases (Visual RAG).
    
    Args:
        image_path: Path to the medical image file
        
    Returns:
        Comprehensive analysis report
    """
    if not os.path.exists(image_path):
        return f"Error: File not found at {image_path}"
        
    report = []
    report.append(f"🔍 ANALYSIS REPORT FOR: {os.path.basename(image_path)}")
    report.append("=" * 50)

    # =========================================================================
    # STEP 1: VISION ANALYSIS (LLaVA / Gemini via OpenRouter)
    # =========================================================================
    print(f"👁️  Phase 1: Analyzing visual features...")
    vision_description = ""
    search_query = ""

    if analyze_medical_image is None:
        report.append("\n❌ Vision analysis unavailable (vision_tool not loaded)")
        search_query = "medical imaging pathology"
    else:
        try:
            vision_description = analyze_medical_image.invoke(image_path)

            # Extract a CONSERVATIVE search query from structured vision output
            search_query = _extract_search_query(vision_description)

            report.append(f"\n📋 VISUAL FINDINGS:\n{vision_description}")

        except Exception as e:
            report.append(f"\n❌ Vision analysis failed: {e}")
            search_query = "medical imaging pathology"

    # =========================================================================
    # STEP 2: SEMANTIC SEARCH with RERANKING (Text Guidelines from diseases DB)
    # Skip when called from trustmed_brain (which does broader 3-collection search)
    # =========================================================================
    if _skip_text_rag:
        print(f"📚 Phase 2: Skipped (brain orchestrator handles broader vector search)")
        report.append("\n📖 RELEVANT GUIDELINES: Deferred to brain orchestrator (3-collection search)")
        text_collection = None  # Skip the entire block
    else:
        print(f"📚 Phase 2: Retrieving medical guidelines...")
        text_collection = get_text_retriever()

    if text_collection:
        try:
            # Fetch more candidates for reranking (2x the final count)
            fetch_k = TEXT_RAG_RERANK_TOP_K * 3 if rerank_documents else TEXT_RAG_RERANK_TOP_K
            text_results = text_collection.query(
                query_texts=[search_query],
                n_results=fetch_k
            )

            report.append("\n📖 RELEVANT GUIDELINES (Text-RAG):")
            if text_results['documents'] and text_results['documents'][0]:
                docs = text_results['documents'][0]
                metas = text_results['metadatas'][0] if text_results['metadatas'] else [{}] * len(docs)

                # Apply cross-encoder reranking if available
                if rerank_documents and len(docs) > 1:
                    print(f"  🔄 Reranking {len(docs)} text-RAG results...")
                    reranked = rerank_documents(
                        search_query, docs, metas,
                        top_k=TEXT_RAG_RERANK_TOP_K,
                        min_score=0.3  # Normalized threshold
                    )
                    if reranked:
                        for i, (doc, score, meta) in enumerate(reranked):
                            src = meta.get('source', meta.get('Disease', 'Unknown'))
                            doc_preview = doc[:250] + "..." if len(doc) > 250 else doc
                            report.append(f"   {i+1}. [{src}] (Relevance: {score:.1%})\n      {doc_preview}")
                        print(f"  ✓ Kept {len(reranked)} after reranking")
                    else:
                        report.append("   No guidelines passed relevance threshold.")
                else:
                    # Fallback: no reranker available
                    for i, doc in enumerate(docs[:TEXT_RAG_RERANK_TOP_K]):
                        meta = metas[i] if i < len(metas) else {}
                        src = meta.get('source', meta.get('Disease', 'Unknown'))
                        doc_preview = doc[:250] + "..." if len(doc) > 250 else doc
                        report.append(f"   {i+1}. [{src}]\n      {doc_preview}")
            else:
                report.append("   No specific guidelines found in knowledge base.")
        except Exception as e:
            report.append(f"   ⚠️ Text search error: {e}")
    else:
        report.append("\n⚠️ Text Knowledge Base not found (Phase 2 skipped).")

    # =========================================================================
    # STEP 3: VISUAL SEARCH with SIMILARITY THRESHOLD (Similar Cases via BiomedCLIP)
    # =========================================================================
    if search_similar_images:
        print(f"🖼️  Phase 3: Searching for similar historical scans...")
        try:
            # Fetch more candidates so we can filter by threshold
            visual_results = search_similar_images(image_path, n_results=5)

            report.append("\n🖼️  SIMILAR HISTORICAL CASES (Visual-RAG):")

            if visual_results and visual_results.get('ids') and visual_results['ids'][0]:
                shown_count = 0
                below_threshold = 0
                for i, (img_id, metadata, distance) in enumerate(zip(
                    visual_results['ids'][0],
                    visual_results['metadatas'][0],
                    visual_results['distances'][0]
                )):
                    similarity = 1 - distance  # Convert distance to similarity

                    # Only show cases above the similarity threshold
                    if similarity < VISUAL_SIMILARITY_THRESHOLD:
                        below_threshold += 1
                        continue

                    shown_count += 1
                    filename = metadata.get('filename', img_id)
                    modality = metadata.get('modality', 'Unknown')
                    caption = metadata.get('caption', '')[:100]
                    label = metadata.get('label', '')  # Ground-truth label if available

                    report.append(f"   {shown_count}. {filename}")
                    report.append(f"      Modality: {modality} | Similarity: {similarity:.2%}")
                    if label:
                        report.append(f"      Ground-Truth Label: {label}")
                    if caption:
                        report.append(f"      Caption: {caption}...")

                    # Limit to top 3 above threshold
                    if shown_count >= 3:
                        break

                if shown_count == 0:
                    report.append(f"   No cases above {VISUAL_SIMILARITY_THRESHOLD:.0%} similarity threshold.")
                    report.append(f"   ({below_threshold} cases found below threshold — excluded to prevent noise)")
                elif below_threshold > 0:
                    report.append(f"   ({below_threshold} additional cases below {VISUAL_SIMILARITY_THRESHOLD:.0%} threshold excluded)")
            else:
                report.append("   No similar cases found in visual database.")

        except Exception as e:
            report.append(f"   ⚠️ Visual search error: {e}")
    else:
        if ENABLE_VISUAL_RAG:
            report.append("\n⚠️ Visual-RAG unavailable (open_clip/ingestion support not loaded).")
        else:
            report.append("\nVisual-RAG disabled by configuration.")

    # =========================================================================
    # STEP 4: CROSS-REFERENCE VALIDATION (Anti-Hallucination)
    # Compare vision model findings against Visual RAG ground-truth labels.
    # If vision says "pneumothorax" but similar images are all "normal",
    # the finding is likely hallucinated and gets downgraded.
    # =========================================================================
    print(f"🔗 Phase 4: Cross-referencing findings against labeled database...")
    report.append("\n🔗 CROSS-REFERENCE VALIDATION:")

    try:
        cross_ref = _cross_reference_findings(vision_description, image_path)
        if cross_ref:
            report.append(cross_ref)
        else:
            report.append("   Skipped — insufficient data for cross-referencing.")
    except Exception as e:
        report.append(f"   ⚠️ Cross-reference error: {e}")

    report.append("\n" + "=" * 50)
    report.append("🏁 Analysis Complete")
    
    return "\n".join(report)


# --- SMART ENTRY POINT ---

@tool
def analyze_medical_image_pipeline(image_path: str) -> str:
    """
    Analyze a medical image with the standard single-image vision pipeline.

    Results are cached by image SHA-256 hash. Re-uploading the same image
    or asking follow-up questions returns the cached result instantly.

    Args:
        image_path: Path to the medical image file

    Returns:
        Comprehensive analysis report
    """
    if not os.path.exists(image_path):
        return f"Error: File not found at {image_path}"

    # ── Cache lookup ──────────────────────────────────────────────
    image_hash = _compute_image_hash(image_path)
    if image_hash in _vision_cache:
        _cache_stats["hits"] += 1
        _vision_cache.move_to_end(image_hash)  # LRU: mark as recently used
        stats = get_vision_cache_stats()
        print(f"⚡ CACHE HIT — returning cached vision result "
              f"(hash: {image_hash[:12]}… | "
              f"hits: {stats['hits']}, rate: {stats['hit_rate']})")
        return _vision_cache[image_hash]

    _cache_stats["misses"] += 1
    print(f"🔄 Cache miss — running full vision pipeline (hash: {image_hash[:12]}…)")

    # ── Run standard single-image analysis ────────────────────────
    result = analyze_and_retrieve_context.invoke(image_path)
    _cache_put(image_hash, result)
    return result


def _cache_put(key: str, value: str):
    """Insert into LRU cache, evicting oldest if at capacity."""
    _vision_cache[key] = value
    _vision_cache.move_to_end(key)
    if len(_vision_cache) > _VISION_CACHE_MAX_SIZE:
        _vision_cache.popitem(last=False)  # Evict oldest


# --- HELPER FUNCTION FOR DIRECT USE ---

def run_full_analysis(image_path: str) -> str:
    """
    Run the complete multimodal analysis pipeline.

    Args:
        image_path: Path to medical image

    Returns:
        Full analysis report
    """
    return analyze_medical_image_pipeline.invoke(image_path)


# --- TEST BLOCK ---

if __name__ == "__main__":
    print("=" * 60)
    print("🧠 Vision Agent - Multimodal Medical Analysis")
    print("=" * 60)
    
    # Test with one of the ingested images
    test_images = [
        "data/medical_images/roco_0000.jpg",
        "data/medical_images/roco_0001.jpg",
        "temp_scan.jpg"
    ]
    
    test_img = None
    for img in test_images:
        if os.path.exists(img):
            test_img = img
            break
    
    if test_img:
        print(f"\n🖼️  Testing with: {test_img}\n")
        result = analyze_and_retrieve_context.invoke(test_img)
        print(result)
    else:
        print("\n⚠️ No test image found.")
        print("Please ensure you have images in data/medical_images/")
        print("Or upload an image via the Streamlit app.")
