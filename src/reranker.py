"""
Reranker Module - Cross-Encoder for Advanced RAG

Upgrades TrustMed AI from "Basic RAG" to "Advanced RAG" by:
1. Taking top-K results from vector search (fast but "dumb")
2. Re-scoring each result with a cross-encoder (slow but smart)
3. Returning only the most relevant results for LLM synthesis

This significantly reduces hallucinations and improves answer quality.

Score Normalization:
  ms-marco cross-encoders output raw logits in the range [-10, +10].
  A score of 0 means "maybe relevant", positive = relevant, negative = irrelevant.
  We apply sigmoid normalization to map scores to [0, 1] for consistent thresholding.
"""

import os
import math
from typing import List, Tuple, Dict, Any
from sentence_transformers import CrossEncoder

# =============================================================================
# Configuration
# =============================================================================

# Cross-encoder model for reranking
# ms-marco models are trained on real search queries - great for RAG
RERANKER_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

# Thresholds (applied AFTER sigmoid normalization to [0, 1] range)
MIN_RELEVANCE_SCORE = 0.3   # Drop results below 30% relevance (sigmoid-normalized)
TOP_K_AFTER_RERANK = 3      # Keep only top 3 after reranking


# =============================================================================
# Score Normalization
# =============================================================================

def normalize_score(raw_score: float) -> float:
    """
    Normalize ms-marco cross-encoder raw logit to [0, 1] via sigmoid.

    Raw ms-marco scores range roughly [-10, +10]:
      - Negative scores = irrelevant
      - Score around 0 = borderline
      - Positive scores = relevant
      - Score > 3 = highly relevant

    Sigmoid maps: -10 → ~0.0, 0 → 0.5, +3 → 0.95, +10 → ~1.0

    Args:
        raw_score: Raw cross-encoder logit

    Returns:
        Normalized score in [0, 1]
    """
    return 1.0 / (1.0 + math.exp(-raw_score))

# =============================================================================
# Reranker Class
# =============================================================================

_reranker = None


def get_reranker() -> CrossEncoder:
    """Lazily initialize the cross-encoder reranker."""
    global _reranker
    
    if _reranker is None:
        print("📊 Loading Reranker model...")
        _reranker = CrossEncoder(RERANKER_MODEL, max_length=512)
        print(f"✅ Reranker loaded: {RERANKER_MODEL}")
    
    return _reranker


def rerank_documents(
    query: str,
    documents: List[str],
    metadatas: List[Dict] = None,
    top_k: int = TOP_K_AFTER_RERANK,
    min_score: float = MIN_RELEVANCE_SCORE
) -> List[Tuple[str, float, Dict]]:
    """
    Rerank documents using cross-encoder for improved relevance.

    Scores are sigmoid-normalized to [0, 1] range for consistent thresholding.

    Args:
        query: The user's question
        documents: List of retrieved document texts
        metadatas: Optional list of metadata dicts for each document
        top_k: Number of top results to return after reranking
        min_score: Minimum normalized relevance score (0-1, default 0.3)

    Returns:
        List of (document, normalized_score, metadata) tuples, sorted by relevance
    """
    if not documents:
        return []

    reranker = get_reranker()

    # Prepare query-document pairs for cross-encoder
    pairs = [[query, doc] for doc in documents]

    # Score all pairs (raw logits)
    raw_scores = reranker.predict(pairs)

    # Normalize scores to [0, 1] via sigmoid
    norm_scores = [normalize_score(float(s)) for s in raw_scores]

    # Combine with documents and metadata
    if metadatas is None:
        metadatas = [{}] * len(documents)

    results = list(zip(documents, norm_scores, metadatas))

    # Sort by normalized score (highest first)
    results.sort(key=lambda x: x[1], reverse=True)

    # Filter by minimum normalized score and take top_k
    filtered = [
        (doc, score, meta)
        for doc, score, meta in results
        if score >= min_score
    ][:top_k]

    return filtered


def rerank_chroma_results(
    query: str,
    chroma_results: Dict[str, Any],
    top_k: int = TOP_K_AFTER_RERANK
) -> Dict[str, Any]:
    """
    Rerank ChromaDB query results.
    
    Args:
        query: The user's question
        chroma_results: Results dict from ChromaDB query()
        top_k: Number of results to keep
        
    Returns:
        Reranked results in same format as ChromaDB
    """
    documents = chroma_results.get('documents', [[]])[0]
    metadatas = chroma_results.get('metadatas', [[]])[0]
    ids = chroma_results.get('ids', [[]])[0]
    
    if not documents:
        return chroma_results
    
    # Create combined list for reranking
    combined = list(zip(documents, metadatas, ids))

    reranker = get_reranker()
    pairs = [[query, doc] for doc in documents]
    raw_scores = reranker.predict(pairs)

    # Normalize scores to [0, 1]
    norm_scores = [normalize_score(float(s)) for s in raw_scores]

    # Sort by normalized score
    scored = list(zip(combined, norm_scores))
    scored.sort(key=lambda x: x[1], reverse=True)

    # Filter by minimum score and take top_k
    top_results = [
        item for item in scored
        if item[1] >= MIN_RELEVANCE_SCORE
    ][:top_k]

    if not top_results:
        # Return empty if nothing passes threshold
        return {'ids': [[]], 'documents': [[]], 'metadatas': [[]], 'distances': [[]], 'reranker_scores': [[]]}

    # Rebuild ChromaDB-style result dict
    reranked = {
        'ids': [[item[0][2] for item in top_results]],
        'documents': [[item[0][0] for item in top_results]],
        'metadatas': [[item[0][1] for item in top_results]],
        'distances': [[1 - item[1] for item in top_results]],  # Convert normalized score to distance
        'reranker_scores': [[item[1] for item in top_results]]  # Normalized [0, 1] scores
    }

    return reranked


def rerank_and_format(
    query: str,
    documents: List[str],
    sources: List[str] = None,
    top_k: int = TOP_K_AFTER_RERANK
) -> str:
    """
    Rerank documents and format as context string.
    
    Args:
        query: User's question
        documents: List of document texts
        sources: Optional list of source labels (e.g., "diseases", "symptoms")
        top_k: Number of results to keep
        
    Returns:
        Formatted string with reranked documents and scores
    """
    if not documents:
        return "No relevant documents found."
    
    if sources is None:
        sources = ["Unknown"] * len(documents)
    
    # Prepare metadata
    metadatas = [{"source": src} for src in sources]
    
    # Rerank
    reranked = rerank_documents(query, documents, metadatas, top_k=top_k)
    
    if not reranked:
        return "No documents passed relevance threshold."
    
    # Format output — scores are already normalized to [0, 1]
    output = []
    for i, (doc, score, meta) in enumerate(reranked, 1):
        source = meta.get("source", "Unknown")
        score_pct = score * 100  # Already in [0, 1] range
        output.append(f"[{source}] (Relevance: {score_pct:.1f}%)\n{doc[:500]}...")
    
    return "\n\n".join(output)


# =============================================================================
# Test
# =============================================================================

if __name__ == "__main__":
    # Test the reranker
    test_query = "What are the symptoms of pneumonia?"
    
    test_docs = [
        "Pneumonia is a lung infection caused by bacteria, viruses, or fungi. Common symptoms include cough, fever, chills, and difficulty breathing.",
        "The history of pneumonia treatment dates back to ancient Greece. Hippocrates described pneumonia in his writings.",
        "Pneumonia symptoms in elderly patients may differ from younger patients. Confusion and weakness are more common.",
        "Bronchitis and pneumonia share some symptoms but have different treatments. Bronchitis affects the airways.",
        "Pneumonia vaccine is recommended for adults over 65 and those with chronic conditions."
    ]
    
    test_sources = ["diseases", "history", "symptoms", "diseases", "medicines"]
    
    print("=" * 60)
    print("🧪 RERANKER TEST")
    print("=" * 60)
    print(f"\nQuery: {test_query}\n")
    print("Before reranking (original order):")
    for i, doc in enumerate(test_docs, 1):
        print(f"  {i}. {doc[:80]}...")
    
    print("\n" + "-" * 40)
    print("After reranking (by relevance):\n")
    
    result = rerank_and_format(test_query, test_docs, test_sources, top_k=3)
    print(result)
