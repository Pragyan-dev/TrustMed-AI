#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Hybrid Search: Combining Vector and Graph Retrieval

This module provides a hybrid search function that queries both:
1. ChromaDB (vector similarity search)
2. Neo4j Knowledge Graph (structured relationship queries)

The searches run in parallel using asyncio for optimal performance.

Usage:
    from hybrid_search import hybrid_search
    
    # Synchronous usage
    result = hybrid_search("What are the symptoms of diabetes?")
    print(result)
    
    # Async usage
    import asyncio
    result = asyncio.run(async_hybrid_search("What drugs treat hypertension?"))
"""

import asyncio
import os
from typing import List, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor
from dotenv import load_dotenv
from src.runtime_config import CHROMA_DB_DIR

# Load environment variables
load_dotenv()

# Import ChromaDB (sentence_transformers imported lazily in _get_embedding_model)
import chromadb

# Import GraphRetriever tool
from src.graph_tool import get_graph_retriever_tool, GraphRetriever


# ----------------------------
# Configuration
# ----------------------------

EMBEDDING_MODEL_NAME = os.getenv("EMBEDDING_MODEL_NAME", "sentence-transformers/all-MiniLM-L6-v2")
VECTOR_TOP_K = 3  # Number of chunks to retrieve from vector search


# ----------------------------
# Vector Search (ChromaDB)
# ----------------------------

# Lazy-loaded globals
_chroma_client: Optional[chromadb.PersistentClient] = None
_embedding_model = None  # Lazy loaded SentenceTransformer


def _get_chroma_client() -> chromadb.PersistentClient:
    """Get or create ChromaDB client."""
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
    return _chroma_client


def _get_embedding_model():
    """Get or create embedding model with lazy import."""
    global _embedding_model
    if _embedding_model is None:
        try:
            from sentence_transformers import SentenceTransformer
            _embedding_model = SentenceTransformer(EMBEDDING_MODEL_NAME)
        except Exception as e:
            print(f"[Warning] Could not load SentenceTransformer: {e}")
            _embedding_model = None
    return _embedding_model


def vector_search(query: str, top_k: int = VECTOR_TOP_K) -> str:
    """
    Retrieve top k chunks from ChromaDB based on vector similarity.
    
    Args:
        query: The search query string.
        top_k: Number of results to return (default: 3).
        
    Returns:
        str: Formatted string of retrieved chunks with metadata.
    """
    try:
        client = _get_chroma_client()
        model = _get_embedding_model()
        
        # Get all collections
        collections = client.list_collections()
        
        if not collections:
            return "[No ChromaDB collections found]"
        
        # Encode query
        query_embedding = model.encode([query])[0].tolist()
        
        # Search across all collections
        all_results = []
        
        for collection in collections:
            try:
                results = collection.query(
                    query_embeddings=[query_embedding],
                    n_results=top_k,
                    include=["documents", "metadatas", "distances"]
                )
                
                if results and results.get("documents") and results["documents"][0]:
                    docs = results["documents"][0]
                    metas = results.get("metadatas", [[]])[0]
                    distances = results.get("distances", [[]])[0]
                    
                    for i, doc in enumerate(docs):
                        meta = metas[i] if i < len(metas) else {}
                        dist = distances[i] if i < len(distances) else None
                        similarity = 1 - dist if dist is not None else 0
                        
                        # Extract key metadata
                        title = meta.get("title") or meta.get("disease_name") or meta.get("name") or "Unknown"
                        source = meta.get("url") or meta.get("source_url") or meta.get("main_url") or ""
                        table = meta.get("table") or collection.name
                        
                        all_results.append({
                            "text": doc[:500] + "..." if len(doc) > 500 else doc,
                            "title": title,
                            "source": source,
                            "collection": table,
                            "similarity": similarity,
                        })
            except Exception as e:
                print(f"[VectorSearch] Error querying collection {collection.name}: {e}")
                continue
        
        if not all_results:
            return "[No relevant documents found in ChromaDB]"
        
        # Sort by similarity and take top k
        all_results.sort(key=lambda x: x["similarity"], reverse=True)
        top_results = all_results[:top_k]
        
        # Format output
        formatted = []
        for i, result in enumerate(top_results, 1):
            formatted.append(
                f"[{i}] {result['title']} (Collection: {result['collection']}, "
                f"Similarity: {result['similarity']:.3f})\n"
                f"{result['text']}"
            )
            if result['source']:
                formatted.append(f"Source: {result['source']}")
            formatted.append("")
        
        return "\n".join(formatted).strip()
        
    except Exception as e:
        return f"[Vector search error: {str(e)}]"


# ----------------------------
# Graph Search (Neo4j)
# ----------------------------

# Lazy-loaded graph retriever
_graph_retriever: Optional[GraphRetriever] = None


def _get_graph_retriever() -> GraphRetriever:
    """Get or create GraphRetriever tool."""
    global _graph_retriever
    if _graph_retriever is None:
        _graph_retriever = get_graph_retriever_tool()
    return _graph_retriever


def graph_search(query: str) -> str:
    """
    Query the Neo4j knowledge graph using the GraphRetriever tool.
    
    Args:
        query: Natural language question about drugs, diseases, or symptoms.
        
    Returns:
        str: Answer from the knowledge graph.
    """
    try:
        retriever = _get_graph_retriever()
        result = retriever.run(query)
        return result if result else "[No results from knowledge graph]"
    except Exception as e:
        return f"[Graph search error: {str(e)}]"


# ----------------------------
# Async Wrappers
# ----------------------------

async def async_vector_search(query: str, executor: ThreadPoolExecutor) -> str:
    """Async wrapper for vector search."""
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(executor, vector_search, query)
        return result
    except Exception as e:
        return f"[Vector search error: {str(e)}]"


async def async_graph_search(query: str, executor: ThreadPoolExecutor) -> str:
    """Async wrapper for graph search."""
    loop = asyncio.get_event_loop()
    try:
        result = await loop.run_in_executor(executor, graph_search, query)
        return result
    except Exception as e:
        return f"[Graph search error: {str(e)}]"


# ----------------------------
# Hybrid Search (Main Function)
# ----------------------------

async def async_hybrid_search(query: str) -> str:
    """
    Perform hybrid search combining vector and graph retrieval in parallel.
    
    This function runs both searches concurrently using asyncio.
    If one search fails, the other still returns results.
    
    Args:
        query: Natural language search query.
        
    Returns:
        str: Combined results in format:
            '--- VECTOR CONTEXT ---\n{vector_results}\n\n--- GRAPH CONTEXT ---\n{graph_results}'
    """
    # Create thread pool executor for running sync functions
    executor = ThreadPoolExecutor(max_workers=2)
    
    try:
        # Run both searches in parallel
        vector_task = async_vector_search(query, executor)
        graph_task = async_graph_search(query, executor)
        
        # Gather results with return_exceptions=True to handle failures gracefully
        results = await asyncio.gather(
            vector_task,
            graph_task,
            return_exceptions=True
        )
        
        # Process results
        vector_results = results[0]
        graph_results = results[1]
        
        # Handle exceptions in results
        if isinstance(vector_results, Exception):
            vector_results = f"[Vector search failed: {str(vector_results)}]"
        
        if isinstance(graph_results, Exception):
            graph_results = f"[Graph search failed: {str(graph_results)}]"
        
        # Combine results
        combined = (
            f"--- VECTOR CONTEXT ---\n{vector_results}\n\n"
            f"--- GRAPH CONTEXT ---\n{graph_results}"
        )
        
        return combined
        
    finally:
        executor.shutdown(wait=False)


def hybrid_search(query: str) -> str:
    """
    Synchronous wrapper for hybrid search.
    
    Performs hybrid search combining vector and graph retrieval in parallel.
    If one search fails, the other still returns results.
    
    Args:
        query: Natural language search query.
        
    Returns:
        str: Combined results in format:
            '--- VECTOR CONTEXT ---\n{vector_results}\n\n--- GRAPH CONTEXT ---\n{graph_results}'
    
    Example:
        >>> result = hybrid_search("What are the symptoms of diabetes?")
        >>> print(result)
        --- VECTOR CONTEXT ---
        [1] Type 2 Diabetes (Collection: diseases, Similarity: 0.856)
        Type 2 diabetes is a chronic condition that affects the way the body...
        
        --- GRAPH CONTEXT ---
        Type 2 Diabetes is associated with the following symptoms: fatigue, 
        increased thirst, frequent urination...
    """
    # Check if there's already a running event loop
    try:
        loop = asyncio.get_running_loop()
        # If we're in an async context, create a new thread to run the async function
        import concurrent.futures
        with concurrent.futures.ThreadPoolExecutor() as pool:
            future = pool.submit(asyncio.run, async_hybrid_search(query))
            return future.result()
    except RuntimeError:
        # No running event loop, safe to use asyncio.run
        return asyncio.run(async_hybrid_search(query))


# ----------------------------
# Convenience Functions
# ----------------------------

def search_and_print(query: str) -> None:
    """Search and print results in a formatted way."""
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print('='*60)
    result = hybrid_search(query)
    print(result)
    print('='*60)


# ----------------------------
# Main (for testing)
# ----------------------------

def main():
    """Test the hybrid search function."""
    print("=" * 60)
    print("Hybrid Search - Test Mode")
    print("=" * 60)
    
    test_queries = [
        "What are the symptoms of diabetes?",
        "What drugs are used to treat high blood pressure?",
        "What causes asthma?",
    ]
    
    for query in test_queries:
        search_and_print(query)
        print("\n")
    
    print("Testing complete!")


if __name__ == "__main__":
    main()
