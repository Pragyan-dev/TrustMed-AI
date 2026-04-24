"""
Hybrid Agent - Neuro-Symbolic Medical AI System

This module combines vector retrieval (ChromaDB) with graph retrieval (Neo4j)
to provide comprehensive medical information using parallel async execution.
"""

import os
import asyncio
from typing import Dict, Any
from dotenv import load_dotenv

import chromadb
from chromadb.utils import embedding_functions
from langchain_openai import ChatOpenAI

from src.graph_tool import GraphRetriever
from src.runtime_config import CHROMA_DB_DIR, CHAT_MAX_TOKENS, SYNTHESIS_TIMEOUT_SECONDS

load_dotenv()

# Configuration
CHROMA_DB_PATH = CHROMA_DB_DIR
EMBEDDING_MODEL = "sentence-transformers/all-MiniLM-L6-v2"
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL", "nvidia/nemotron-3-nano-30b-a3b:free")

# Lazy-loaded globals
_chroma_client = None
_embedding_fn = None
_collections = {}


def get_chroma_client() -> chromadb.PersistentClient:
    """Lazily initialize ChromaDB client."""
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=CHROMA_DB_PATH)
    return _chroma_client


def get_embedding_function():
    """Lazily initialize the embedding function."""
    global _embedding_fn
    if _embedding_fn is None:
        _embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name=EMBEDDING_MODEL
        )
    return _embedding_fn


def get_collection(name: str):
    """Get or create a ChromaDB collection."""
    global _collections
    if name not in _collections:
        client = get_chroma_client()
        # Don't pass embedding_function - use the one already persisted in the collection
        _collections[name] = client.get_collection(name=name)
    return _collections[name]


# =============================================================================
# 1. Vector Retrieval (ChromaDB)
# =============================================================================

def vector_search(query: str, top_k: int = 3) -> str:
    """
    Query medicines, diseases, and symptoms collections in ChromaDB.
    
    Args:
        query: The search query string.
        top_k: Number of results per collection (default 3).
        
    Returns:
        Concatenated context string from all collections.
    """
    collection_names = ["medicines", "diseases", "symptoms"]
    all_chunks = []
    
    for col_name in collection_names:
        try:
            collection = get_collection(col_name)
            results = collection.query(
                query_texts=[query],
                n_results=top_k
            )
            
            # Extract documents from results
            documents = results.get("documents", [[]])[0]
            if documents:
                header = f"[{col_name.upper()}]"
                for doc in documents:
                    all_chunks.append(f"{header}\n{doc}")
                    
        except Exception as e:
            print(f"[VectorSearch] Error querying {col_name}: {e}")
            continue
    
    if not all_chunks:
        return "No relevant clinical text found."
    
    return "\n\n".join(all_chunks)


# =============================================================================
# 2. Graph Retrieval (Neo4j via GraphRetriever)
# =============================================================================

def graph_search(query: str) -> str:
    """
    Query the Neo4j knowledge graph using the GraphRetriever tool.
    
    Args:
        query: Natural language medical question.
        
    Returns:
        Graph query results or error message.
    """
    try:
        result = GraphRetriever.invoke(query)
        return result if result else "No structured data found"
    except Exception as e:
        print(f"[GraphSearch] Error: {e}")
        return "No structured data found"


# =============================================================================
# 3. Fusion Logic (Async Parallel Execution)
# =============================================================================

async def _async_vector_search(query: str) -> str:
    """Async wrapper for vector search."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, vector_search, query)


async def _async_graph_search(query: str) -> str:
    """Async wrapper for graph search."""
    loop = asyncio.get_event_loop()
    return await loop.run_in_executor(None, graph_search, query)


async def hybrid_search(query: str) -> Dict[str, Any]:
    """
    Execute vector and graph searches in parallel and fuse results.
    
    Args:
        query: The medical query string.
        
    Returns:
        Dictionary containing:
            - vector_context: Raw ChromaDB results
            - graph_context: Raw Neo4j results  
            - combined_context: Formatted fusion of both sources
    """
    # Run both searches in parallel
    vector_result, graph_result = await asyncio.gather(
        _async_vector_search(query),
        _async_graph_search(query),
        return_exceptions=True
    )
    
    # Handle exceptions gracefully
    if isinstance(vector_result, Exception):
        print(f"[HybridSearch] Vector search failed: {vector_result}")
        vector_result = "No relevant clinical text found."
        
    if isinstance(graph_result, Exception):
        print(f"[HybridSearch] Graph search failed: {graph_result}")
        graph_result = "No structured data found"
    
    # Format combined context
    combined = (
        f"--- CLINICAL TEXT ---\n{vector_result}\n\n"
        f"--- KNOWLEDGE GRAPH FACTS ---\n{graph_result}"
    )
    
    return {
        "vector_context": vector_result,
        "graph_context": graph_result,
        "combined_context": combined
    }


# =============================================================================
# 4. Synthesis (Final Answer Generation)
# =============================================================================

SYSTEM_PROMPT = """You are TrustMed AI, a medical information assistant.

Answer the query using ONLY the provided context. Follow these rules:
1. If the Knowledge Graph Facts contradict the Clinical Text, PRIORITIZE the Knowledge Graph as it is clinically verified.
2. Cite your sources (e.g., "According to the knowledge graph..." or "Clinical records indicate...").
3. If neither source provides relevant information, clearly state that.
4. Do not make up information not present in the context.
5. Be concise but thorough."""


def generate_response(query: str, context: str) -> str:
    """
    Generate a response using the LLM with the combined context.
    
    Args:
        query: The original user query.
        context: The combined context from hybrid search.
        
    Returns:
        The generated response string.
    """
    try:
        llm = ChatOpenAI(
            model=OPENROUTER_MODEL,
            openai_api_key=OPENROUTER_API_KEY,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=0.3,
            max_tokens=CHAT_MAX_TOKENS,
            request_timeout=SYNTHESIS_TIMEOUT_SECONDS,
        )
        
        messages = [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": f"Context:\n{context}\n\nQuery: {query}"}
        ]
        
        response = llm.invoke(messages)
        return response.content
        
    except Exception as e:
        print(f"[GenerateResponse] Error: {e}")
        return f"I encountered an error generating a response: {str(e)}"


# =============================================================================
# Main Entry Point
# =============================================================================

async def ask(query: str) -> Dict[str, Any]:
    """
    Main entry point for the Neuro-Symbolic system.
    
    Args:
        query: User's medical question.
        
    Returns:
        Dictionary with search results and final response.
    """
    print(f"\n{'='*60}")
    print(f"Query: {query}")
    print('='*60)
    
    # Perform hybrid search
    search_results = await hybrid_search(query)
    
    print("\n[Vector Context]")
    print(search_results["vector_context"][:500] + "..." if len(search_results["vector_context"]) > 500 else search_results["vector_context"])
    
    print("\n[Graph Context]")
    print(search_results["graph_context"])
    
    # Generate final response
    final_response = generate_response(query, search_results["combined_context"])
    
    print("\n[TrustMed AI Response]")
    print(final_response)
    
    return {
        **search_results,
        "response": final_response
    }


def run(query: str) -> Dict[str, Any]:
    """Synchronous wrapper for the ask function."""
    return asyncio.run(ask(query))


if __name__ == "__main__":
    # Test query
    test_query = "What are the symptoms of diabetes and how is it treated?"
    result = run(test_query)
    print("\n" + "="*60)
    print("FINAL RESULT:")
    print(result["response"])
