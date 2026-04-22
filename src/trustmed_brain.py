"""
TrustMed Brain - Neuro-Symbolic Medical AI Orchestrator

This module combines three knowledge sources:
- Right Brain (Vector): ChromaDB semantic search over medical literature
- Left Brain (Graph): Neo4j knowledge graph with verified medical facts
- Patient Context: Real-time patient data from MIMIC (vitals, diagnoses, meds)

The orchestrator fuses these contexts and generates comprehensive medical insights.
"""

import asyncio
import re
import os
from dotenv import load_dotenv

import chromadb
from sentence_transformers import SentenceTransformer
from langchain_neo4j import GraphCypherQAChain
from langchain_openai import ChatOpenAI
from langchain_core.prompts import PromptTemplate

from src.patient_context_tool import get_patient_vitals, get_patient_diagnoses, get_patient_meds
# Upgraded: Full Multimodal Vision Agent (Vision + Text RAG + Visual RAG)
# Uses compound-aware entry point that auto-detects multi-panel figures (MedICaT-inspired)
from src.vision_agent import (
    analyze_with_compound_support, set_skip_text_rag,
    get_vision_cache_stats, clear_vision_cache
)
from src.vision_tool import set_preferred_vision_model
# Advanced RAG: Cross-Encoder Reranker for improved retrieval quality
from src.reranker import rerank_documents, get_reranker
from src.ssl_bootstrap import configure_ssl_certificates, get_ssl_cert_path, get_ssl_context

# Neo4j import: prefer langchain-neo4j package (new), fall back to langchain-community (deprecated)
try:
    from langchain_neo4j import Neo4jGraph
except ImportError:
    from langchain_community.graphs import Neo4jGraph

load_dotenv()
configure_ssl_certificates()

# =============================================================================
# Configuration
# =============================================================================

CHROMA_DB_DIR = "./data/chroma_db"

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY")
DEFAULT_OPENROUTER_MODEL = "nvidia/nemotron-3-nano-30b-a3b:free"
OPENROUTER_MODEL = os.getenv("OPENROUTER_MODEL") or DEFAULT_OPENROUTER_MODEL

# Safety Critic: MUST be a DIFFERENT model from the synthesizer to avoid self-grading
# Using a different architecture ensures genuinely independent review
SAFETY_CRITIC_MODEL = os.getenv(
    "SAFETY_CRITIC_MODEL",
    "google/gemma-3n-e4b-it:free"  # Different architecture from synthesizer
)
# Fallback models when primary safety critic is rate-limited (429)
SAFETY_CRITIC_FALLBACKS = [
    "google/gemma-3-4b-it:free",
    "meta-llama/llama-3.1-8b-instruct:free",
    "mistralai/mistral-small-3.1-24b-instruct:free",
]
SAFETY_CRITIC_TEMPERATURE = 0.3  # Slightly higher than synth (0.1) for broader scrutiny

# Vertex AI MedGemma configuration (reuse from .env)
VERTEX_PROJECT_ID = os.getenv('VERTEX_PROJECT_ID', '')
VERTEX_ENDPOINT_ID = os.getenv('VERTEX_ENDPOINT_ID', '')
VERTEX_REGION = os.getenv('VERTEX_REGION', 'us-central1')
VERTEX_SA_JSON = os.getenv('VERTEX_SERVICE_ACCOUNT_JSON', '')
VERTEX_DEDICATED_DOMAIN = os.getenv('VERTEX_DEDICATED_DOMAIN', '')

# Patient ID regex pattern (8-digit IDs starting with 10)
PATIENT_ID_PATTERN = r'\b(10\d{6})\b'

# Image attachment pattern
IMAGE_ATTACHMENT_PATTERN = r'\[ATTACHMENT: (.*?)\]'


# =============================================================================
# Vertex AI MedGemma Text Helper
# =============================================================================

def _get_vertex_credentials():
    """Get Google Cloud credentials for Vertex AI."""
    import google.auth
    import google.auth.transport.requests as google_requests

    if VERTEX_SA_JSON and os.path.exists(VERTEX_SA_JSON):
        from google.oauth2 import service_account
        credentials = service_account.Credentials.from_service_account_file(
            VERTEX_SA_JSON, scopes=['https://www.googleapis.com/auth/cloud-platform']
        )
    else:
        credentials, _ = google.auth.default(
            scopes=['https://www.googleapis.com/auth/cloud-platform']
        )

    auth_req = google_requests.Request()
    credentials.refresh(auth_req)
    return credentials


def call_medgemma_text(prompt: str, temperature: float = 0.1,
                       max_tokens: int = 2000, stream: bool = False):
    """
    Call MedGemma 27B on Vertex AI for text-only synthesis (no image).

    Args:
        prompt: The text prompt to send
        temperature: Sampling temperature
        max_tokens: Max response tokens
        stream: If True, returns a generator yielding content chunks

    Returns:
        If stream=False: complete response string
        If stream=True: generator yielding content chunk strings
    """
    import requests as _requests

    if not VERTEX_DEDICATED_DOMAIN or not VERTEX_PROJECT_ID or not VERTEX_ENDPOINT_ID:
        raise ValueError(
            "Vertex AI env vars (VERTEX_DEDICATED_DOMAIN, VERTEX_PROJECT_ID, "
            "VERTEX_ENDPOINT_ID) must be set to use MedGemma for text."
        )

    credentials = _get_vertex_credentials()

    base_url = (
        f"https://{VERTEX_DEDICATED_DOMAIN}"
        f"/v1beta1/projects/{VERTEX_PROJECT_ID}"
        f"/locations/{VERTEX_REGION}"
        f"/endpoints/{VERTEX_ENDPOINT_ID}"
    )
    url = f"{base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {credentials.token}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": "google_medgemma-27b-it",
        "messages": [{"role": "user", "content": prompt}],
        "temperature": temperature,
        "max_tokens": max_tokens,
        "stream": stream,
    }

    if not stream:
        resp = _requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=120,
            verify=get_ssl_cert_path() or True,
        )
        if resp.status_code != 200:
            raise ValueError(f"MedGemma text returned {resp.status_code}: {resp.text[:500]}")
        data = resp.json()
        content = (
            data.get("choices", [{}])[0]
            .get("message", {})
            .get("content", "")
        )
        if not content:
            raise ValueError(f"MedGemma returned empty content: {str(data)[:500]}")
        return content
    else:
        # Streaming: return generator that yields content chunks
        resp = _requests.post(
            url,
            headers=headers,
            json=payload,
            timeout=120,
            stream=True,
            verify=get_ssl_cert_path() or True,
        )
        if resp.status_code != 200:
            raise ValueError(f"MedGemma stream returned {resp.status_code}: {resp.text[:500]}")
        return _stream_medgemma_chunks(resp)


def _stream_medgemma_chunks(resp):
    """Parse SSE stream from MedGemma vLLM endpoint and yield content deltas."""
    import json as _json
    for line in resp.iter_lines(decode_unicode=True):
        if not line or not line.startswith("data: "):
            continue
        data_str = line[6:]  # strip "data: "
        if data_str.strip() == "[DONE]":
            break
        try:
            chunk = _json.loads(data_str)
            delta = chunk.get("choices", [{}])[0].get("delta", {}).get("content", "")
            if delta:
                yield delta
        except _json.JSONDecodeError:
            continue


def _invoke_with_retry(llm_factory, prompt, max_retries=3, models=None):
    """
    Invoke an LLM with retry on 429 rate-limit errors.
    Falls back to alternative models if provided.

    Args:
        llm_factory: callable(model_name) -> ChatOpenAI instance
        prompt: the prompt string to invoke
        max_retries: retries per model
        models: list of model names to try in order
    Returns:
        LLM response content string
    Raises:
        last exception if all retries/models exhausted
    """
    import time

    if not models:
        models = [None]  # single attempt with whatever llm_factory returns

    last_exc = None
    for model_name in models:
        llm = llm_factory(model_name) if model_name else llm_factory(None)
        for attempt in range(max_retries):
            try:
                return llm.invoke(prompt).content
            except Exception as e:
                last_exc = e
                err_str = str(e)
                if "429" in err_str or "rate" in err_str.lower():
                    wait = 2 ** attempt  # 1s, 2s, 4s
                    print(f"  ⏳ Rate-limited (429), retry {attempt+1}/{max_retries} "
                          f"in {wait}s (model: {model_name or 'default'})...")
                    time.sleep(wait)
                else:
                    raise  # Non-rate-limit error, don't retry
        # All retries exhausted for this model, try next
        if model_name:
            print(f"  ↩️ Model {model_name} exhausted retries, trying next fallback...")

    raise last_exc

# =============================================================================
# Right Brain: Vector Search (ChromaDB)
# =============================================================================

_chroma_client = None
_embedding_model = None


def get_chroma_client():
    """Lazily initialize ChromaDB client."""
    global _chroma_client
    if _chroma_client is None:
        _chroma_client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
    return _chroma_client


def get_embedding_model():
    """Lazily initialize embedding model."""
    global _embedding_model
    if _embedding_model is None:
        _embedding_model = SentenceTransformer('all-MiniLM-L6-v2')
    return _embedding_model


def get_vector_context(query: str, k: int = 5, use_reranker: bool = True) -> str:
    """
    Search ChromaDB for relevant medical literature with optional reranking.
    
    Args:
        query: Search query
        k: Number of results per collection (before reranking)
        use_reranker: Whether to apply cross-encoder reranking
        
    Returns:
        Consolidated string of relevant medical text
    """
    client = get_chroma_client()
    collections = ['medicines', 'diseases', 'symptoms']
    all_documents = []
    all_sources = []
    
    # Fetch more results if reranking (we'll filter down)
    fetch_k = k * 2 if use_reranker else k
    
    for col_name in collections:
        try:
            collection = client.get_collection(name=col_name)
            results = collection.query(query_texts=[query], n_results=fetch_k)
            
            documents = results.get('documents', [[]])[0]
            for doc in documents:
                all_documents.append(doc)
                all_sources.append(col_name.upper())
                
        except Exception as e:
            print(f"[VectorSearch] Error querying {col_name}: {e}")
            continue
    
    if not all_documents:
        return "No relevant literature found."
    
    # Apply reranking if enabled
    if use_reranker and len(all_documents) > 0:
        print(f"  🔄 Reranking {len(all_documents)} documents...")
        metadatas = [{"source": src} for src in all_sources]
        reranked = rerank_documents(query, all_documents, metadatas, top_k=k)
        
        if reranked:
            formatted = []
            for doc, score, meta in reranked:
                src = meta.get("source", "UNKNOWN")
                # Scores are now sigmoid-normalized to [0, 1]
                formatted.append(f"[{src}] (Relevance: {score:.1%})\n{doc}")
            print(f"  ✓ Kept top {len(reranked)} after reranking")
            return "\n\n".join(formatted)
    
    # Fallback: no reranking
    all_results = [f"[{src}]\n{doc}" for doc, src in zip(all_documents[:k*3], all_sources[:k*3])]
    return "\n\n".join(all_results)


def get_vector_context_fast(query: str, k: int = 5) -> str:
    """
    Faster vector search path for interactive streaming requests.

    This skips the cross-encoder reranker to avoid long first-request stalls
    from model loading/downloading and keeps the streaming pipeline responsive.
    """
    return get_vector_context(query=query, k=k, use_reranker=False)


# =============================================================================
# Left Brain: Graph Search (Neo4j)
# =============================================================================

_neo4j_graph = None
_graph_chain = None
_graph_chain_model = None

# Custom Cypher prompt with fuzzy matching
# NOTE: Only reference node types & relationships that EXIST in the graph.
# Current graph has: Disease, Symptom, Precaution nodes
#                    HAS_SYMPTOM, HAS_PRECAUTION relationships
# Drug nodes & TREATS/INTERACTS_WITH will be added after KG enrichment.
CYPHER_TEMPLATE = """Task: Generate a Cypher statement to query a medical knowledge graph.

Instructions:
- Use ONLY nodes and relationships that exist in the schema below.
- ALWAYS use fuzzy matching: toLower(n.name) CONTAINS toLower("search_term")
- Return relevant properties: name, description, severity, cui
- When looking for symptoms: MATCH (d:Disease)-[:HAS_SYMPTOM]->(s:Symptom)
- For precautions: MATCH (d:Disease)-[:HAS_PRECAUTION]->(p:Precaution)
- Write a SINGLE flat Cypher query. Do NOT nest MATCH clauses.
- Use OPTIONAL MATCH only at the TOP LEVEL, never inside parentheses or RETURN.
- Keep it simple: one MATCH, optional OPTIONAL MATCH, then RETURN.

Schema:
{schema}

Question: {question}

Cypher Query:"""

CYPHER_PROMPT = PromptTemplate(
    input_variables=["schema", "question"],
    template=CYPHER_TEMPLATE
)


def _resolve_graph_model(model_name: str = None) -> str:
    """Use the selected OpenRouter text model for graph work when supported."""
    if model_name and not model_name.startswith("vertex/"):
        return model_name
    return OPENROUTER_MODEL


def get_graph_chain(model_name: str = None):
    """Lazily initialize Neo4j graph and chain."""
    global _neo4j_graph, _graph_chain, _graph_chain_model
    resolved_model = _resolve_graph_model(model_name)
    
    if _graph_chain is None or _graph_chain_model != resolved_model:
        try:
            # Test connection first with a short timeout to avoid hanging
            from neo4j import GraphDatabase
            _test_driver = GraphDatabase.driver(
                NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
                connection_timeout=10,       # 10s connection timeout
                max_transaction_retry_time=5, # 5s max retry
            )
            _test_driver.verify_connectivity()
            _test_driver.close()
            print("  ✓ Neo4j connectivity verified")
        except Exception as conn_err:
            print(f"  ✗ Neo4j connection failed: {conn_err}")
            raise ConnectionError(
                f"Cannot connect to Neo4j ({NEO4J_URI}). "
                f"Check that the Aura instance is running and that the local "
                f"Python CA bundle is configured correctly."
            ) from conn_err

        _neo4j_graph = Neo4jGraph(
            url=NEO4J_URI,
            username=NEO4J_USERNAME,
            password=NEO4J_PASSWORD
        )
        
        llm = ChatOpenAI(
            model=resolved_model,
            openai_api_key=OPENROUTER_API_KEY,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=0,
            request_timeout=20  # 20s timeout to prevent hanging
        )
        
        _graph_chain = GraphCypherQAChain.from_llm(
            llm=llm,
            graph=_neo4j_graph,
            cypher_prompt=CYPHER_PROMPT,
            validate_cypher=True,
            top_k=5,
            verbose=True,
            allow_dangerous_requests=True
        )
        _graph_chain_model = resolved_model
    
    return _graph_chain


def get_graph_context(query: str, model_name: str = None) -> str:
    """Query the knowledge graph. Fails gracefully if Neo4j is unavailable."""
    try:
        chain = get_graph_chain(model_name)
        result = chain.invoke({"query": query})
        answer = result.get("result", "")
        return answer if answer else "No structured data found."
    except ConnectionError as ce:
        print(f"[GraphSearch] Connection Error: {ce}")
        return "Knowledge graph unavailable (Neo4j connectivity issue). Using other sources."
    except Exception as e:
        err_msg = str(e)
        if any(token in err_msg.lower() for token in ("routing", "connect", "certificate", "ssl")):
            print(f"[GraphSearch] Neo4j unreachable: {e}")
            return "Knowledge graph unavailable (Neo4j connectivity issue). Using other sources."
        print(f"[GraphSearch] Error: {e}")
        return "No structured data found."


# =============================================================================
# Patient Context (MIMIC Data)
# =============================================================================

def get_patient_context(query: str, patient_id: str = None) -> str:
    """
    Extract patient ID from query and fetch their medical context.
    
    Args:
        query: User query potentially containing a patient ID
        
    Returns:
        Formatted patient context or empty string if no ID found
    """
    resolved_patient_id = str(patient_id).strip() if patient_id else None
    if not resolved_patient_id:
        match = re.search(PATIENT_ID_PATTERN, query)
        if not match:
            return ""
        resolved_patient_id = match.group(1)

    print(f"\n[PatientContext] Detected Patient ID: {resolved_patient_id}")
    
    try:
        vitals = get_patient_vitals.invoke(resolved_patient_id)
        diagnoses = get_patient_diagnoses.invoke(resolved_patient_id)
        meds = get_patient_meds.invoke(resolved_patient_id)
        
        return f"""
=== PATIENT CONTEXT (ID: {resolved_patient_id}) ===

{vitals}

{diagnoses}

{meds}
"""
    except Exception as e:
        print(f"[PatientContext] Error: {e}")
        return f"Error fetching patient data for ID {resolved_patient_id}"


# =============================================================================
# Deterministic Drug Interaction Checker (Neuro-Symbolic, No LLM)
# =============================================================================

_neo4j_driver = None


def _get_neo4j_driver():
    """Lazily initialize a direct Neo4j driver for deterministic queries."""
    global _neo4j_driver
    if _neo4j_driver is None:
        try:
            from neo4j import GraphDatabase
            _neo4j_driver = GraphDatabase.driver(
                NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD),
                connection_timeout=5,              # 5s connection timeout
                max_transaction_retry_time=5,      # 5s max retry
            )
            # Verify connectivity upfront so we fail fast instead of hanging on session.run()
            _neo4j_driver.verify_connectivity()
            print("[DrugChecker] ✓ Neo4j driver connected")
        except Exception as e:
            print(f"[DrugChecker] Failed to connect to Neo4j: {e}")
            _neo4j_driver = None  # Reset so next call retries
    return _neo4j_driver


def check_drug_interactions(patient_context: str) -> str:
    """
    Deterministic drug interaction checker — queries the Knowledge Graph
    directly without any LLM involvement.

    Extracts medication names from patient context, then queries Neo4j for:
    1. Drug-drug interactions (INTERACTS_WITH)
    2. Drug-condition contraindications (CONTRAINDICATED_WITH)

    This is TRUE neuro-symbolic reasoning: structured graph traversal
    producing factual alerts, not LLM prose generation.

    Args:
        patient_context: Patient context string containing medication list

    Returns:
        Formatted string of drug interaction alerts, or empty string if none found
    """
    driver = _get_neo4j_driver()
    if not driver:
        return ""

    # Extract medication names from patient context
    patient_meds = _extract_medication_names(patient_context)
    if not patient_meds:
        return ""

    # Extract diagnosis names from patient context
    patient_diagnoses = _extract_diagnosis_names(patient_context)

    alerts = []

    # Limit to prevent O(n²) explosion — cap at 10 meds, 5 diagnoses
    patient_meds = patient_meds[:10]
    patient_diagnoses = patient_diagnoses[:5]

    print(f"  [DrugChecker] Found {len(patient_meds)} meds: {patient_meds}")
    print(f"  [DrugChecker] Found {len(patient_diagnoses)} diagnoses: {patient_diagnoses[:3]}...")

    try:
        with driver.session() as session:
            # 1. Check drug-drug interactions — single batch query for all meds
            if len(patient_meds) >= 2:
                result = session.run("""
                    MATCH (d1:Drug)-[r:INTERACTS_WITH]-(d2:Drug)
                    WHERE ANY(med IN $meds WHERE toLower(d1.name) CONTAINS toLower(med))
                      AND ANY(med IN $meds WHERE toLower(d2.name) CONTAINS toLower(med))
                      AND elementId(d1) < elementId(d2)
                    RETURN d1.name as drug1, d2.name as drug2,
                           r.severity as severity, r.effect as effect
                    LIMIT 10
                """, meds=patient_meds)

                for record in result:
                    severity_icon = "🔴" if record["severity"] == "major" else "🟡"
                    alerts.append(
                        f"{severity_icon} DRUG INTERACTION [{record['severity'].upper()}]: "
                        f"{record['drug1']} + {record['drug2']}\n"
                        f"   Effect: {record['effect']}"
                    )

            # 2. Check drug-condition contraindications — single batch query
            if patient_meds and patient_diagnoses:
                result = session.run("""
                    MATCH (drug:Drug)-[r:CONTRAINDICATED_WITH]->(cond)
                    WHERE ANY(med IN $meds WHERE toLower(drug.name) CONTAINS toLower(med))
                      AND ANY(diag IN $diags WHERE
                              toLower(cond.name) CONTAINS toLower(diag)
                              OR toLower(diag) CONTAINS toLower(cond.name))
                    RETURN drug.name as drug, cond.name as condition,
                           r.severity as severity, r.reason as reason
                    LIMIT 10
                """, meds=patient_meds, diags=patient_diagnoses)

                for record in result:
                    severity_icon = "🔴" if record["severity"] == "major" else "🟡"
                    alerts.append(
                        f"{severity_icon} CONTRAINDICATION [{record['severity'].upper()}]: "
                        f"{record['drug']} with {record['condition']}\n"
                        f"   Reason: {record['reason']}"
                    )

            # 3. Get treatment recommendations — single batch query for top diagnoses
            treatment_info = []
            if patient_diagnoses:
                result = session.run("""
                    MATCH (drug:Drug)-[r:TREATS]->(d:Disease)
                    WHERE ANY(diag IN $diags WHERE toLower(d.name) CONTAINS toLower(diag))
                    RETURN d.name as disease, drug.name as drug, drug.drug_class as class,
                           drug.common_dosage as dosage, r.line as line, r.notes as notes
                    ORDER BY d.name, r.line
                    LIMIT 12
                """, diags=patient_diagnoses[:3])

                treatments = list(result)
                if treatments:
                    # Group by disease
                    current_disease = None
                    for t in treatments:
                        if t["disease"] != current_disease:
                            current_disease = t["disease"]
                            treatment_info.append(f"\n  Treatments for {current_disease}:")
                        line_tag = "1st" if t["line"] == "first_line" else "2nd"
                        treatment_info.append(
                            f"    [{line_tag}] {t['drug']} ({t['class']}) — {t['dosage']}"
                        )

    except Exception as e:
        print(f"[DrugChecker] Error querying Neo4j: {e}")
        return ""

    # =========================================================================
    # NEW CHECKS (4-8): Deterministic rule-based safety engine
    # These use hardcoded clinical rules — no LLM, no graph queries needed.
    # =========================================================================

    # --- 4. Duplicate Therapy Detection ---
    # Query Neo4j for drug classes, flag when 2+ meds share a class
    try:
        if driver and len(patient_meds) >= 2:
            with driver.session() as session:
                result = session.run("""
                    MATCH (d:Drug)
                    WHERE ANY(med IN $meds WHERE toLower(d.name) CONTAINS toLower(med))
                    RETURN d.name as drug, d.drug_class as drug_class
                """, meds=patient_meds)
                drug_classes = {}
                for record in result:
                    cls = record["drug_class"]
                    if cls:
                        drug_classes.setdefault(cls, []).append(record["drug"])
                for cls, drugs in drug_classes.items():
                    if len(drugs) >= 2:
                        alerts.append(
                            f"🟡 DUPLICATE THERAPY [{cls}]: "
                            f"Patient is on {len(drugs)} drugs in the same class: {', '.join(drugs)}\n"
                            f"   Risk: Additive side effects, no additional efficacy. "
                            f"Consider deprescribing one."
                        )
    except Exception as e:
        print(f"  [DrugChecker] Duplicate therapy check failed: {e}")

    # --- 5. QT Prolongation Risk Bundle ---
    _QT_RISK_CLASSES = {
        "macrolide", "fluoroquinolone", "antipsychotic", "ssri", "snri",
        "anticonvulsant", "azole antifungal", "antiemetic", "tricyclic antidepressant",
    }
    _QT_RISK_DRUGS = {
        "amiodarone", "sotalol", "haloperidol", "methadone", "ondansetron",
        "erythromycin", "azithromycin", "ciprofloxacin", "levofloxacin",
        "risperidone", "quetiapine", "ziprasidone", "citalopram", "escitalopram",
        "fluconazole", "domperidone", "chloroquine", "hydroxychloroquine",
    }
    qt_drugs_found = []
    try:
        if driver:
            with driver.session() as session:
                result = session.run("""
                    MATCH (d:Drug)
                    WHERE ANY(med IN $meds WHERE toLower(d.name) CONTAINS toLower(med))
                    RETURN d.name as drug, d.drug_class as drug_class
                """, meds=patient_meds)
                for record in result:
                    name_lower = record["drug"].lower()
                    cls_lower = (record["drug_class"] or "").lower()
                    if any(qc in cls_lower for qc in _QT_RISK_CLASSES) or name_lower in _QT_RISK_DRUGS:
                        qt_drugs_found.append(record["drug"])
        # Also check meds directly (in case not in Neo4j)
        for med in patient_meds:
            if med.lower() in _QT_RISK_DRUGS and med.lower() not in [d.lower() for d in qt_drugs_found]:
                qt_drugs_found.append(med)
        if len(qt_drugs_found) >= 2:
            alerts.append(
                f"🔴 QT PROLONGATION RISK: Patient is on {len(qt_drugs_found)} QT-prolonging medications: "
                f"{', '.join(qt_drugs_found)}\n"
                f"   Risk: Additive QT prolongation → Torsades de Pointes. "
                f"Consider ECG monitoring and review necessity of each agent."
            )
        elif len(qt_drugs_found) == 1:
            alerts.append(
                f"🟡 QT PROLONGATION NOTE: {qt_drugs_found[0]} can prolong QT interval.\n"
                f"   Monitor if adding other QT-prolonging agents. "
                f"Check baseline ECG if not done recently."
            )
    except Exception as e:
        print(f"  [DrugChecker] QT check failed: {e}")

    # --- 6. Bleeding Risk Bundle ---
    _BLEEDING_RISK_CLASSES = {
        "anticoagulant", "antiplatelet", "nsaid", "ssri", "snri",
        "thrombolytic", "direct oral anticoagulant",
    }
    _BLEEDING_RISK_DRUGS = {
        "warfarin", "heparin", "enoxaparin", "rivaroxaban", "apixaban",
        "dabigatran", "aspirin", "clopidogrel", "ticagrelor", "prasugrel",
        "ibuprofen", "naproxen", "diclofenac", "ketorolac", "fish oil",
    }
    bleeding_drugs_found = []
    try:
        if driver:
            with driver.session() as session:
                result = session.run("""
                    MATCH (d:Drug)
                    WHERE ANY(med IN $meds WHERE toLower(d.name) CONTAINS toLower(med))
                    RETURN d.name as drug, d.drug_class as drug_class
                """, meds=patient_meds)
                for record in result:
                    name_lower = record["drug"].lower()
                    cls_lower = (record["drug_class"] or "").lower()
                    if any(bc in cls_lower for bc in _BLEEDING_RISK_CLASSES) or name_lower in _BLEEDING_RISK_DRUGS:
                        bleeding_drugs_found.append(record["drug"])
        for med in patient_meds:
            if med.lower() in _BLEEDING_RISK_DRUGS and med.lower() not in [d.lower() for d in bleeding_drugs_found]:
                bleeding_drugs_found.append(med)
        if len(bleeding_drugs_found) >= 2:
            alerts.append(
                f"🔴 BLEEDING RISK: Patient is on {len(bleeding_drugs_found)} agents that increase bleeding: "
                f"{', '.join(bleeding_drugs_found)}\n"
                f"   Risk: Synergistic bleeding risk. Monitor CBC/platelets, "
                f"watch for signs of GI bleed, bruising, hematuria."
            )
    except Exception as e:
        print(f"  [DrugChecker] Bleeding check failed: {e}")

    # --- 7. Renal/Hepatic Dose Warnings ---
    _RENAL_ADJUST_DRUGS = {
        "metformin": "Contraindicated if eGFR <30; reduce dose if eGFR 30-45",
        "vancomycin": "Requires therapeutic drug monitoring; adjust dose per renal function",
        "gabapentin": "Reduce dose: 300mg/day if CrCl 15-29; 300mg QOD if CrCl <15",
        "pregabalin": "Reduce dose proportionally with CrCl",
        "allopurinol": "Start 100mg/day if CrCl <60; max 200mg/day if CrCl <30",
        "methotrexate": "Contraindicated if CrCl <30; reduce dose if CrCl 30-60",
        "lithium": "Reduce dose; narrow therapeutic index worsened by renal impairment",
        "digoxin": "Reduce dose; primarily renally cleared",
        "enoxaparin": "Reduce to 1mg/kg daily (from BID) if CrCl <30",
        "ciprofloxacin": "Reduce to 250-500mg q12h if CrCl <30",
        "acyclovir": "Adjust dose interval based on CrCl",
        "tenofovir": "Adjust dose interval: q48h if CrCl 30-49; avoid if <30",
        "meropenem": "Reduce dose/extend interval if CrCl <50",
    }
    _HEPATIC_ADJUST_DRUGS = {
        "methotrexate": "Hepatotoxic; avoid in significant liver disease",
        "acetaminophen": "Max 2g/day in liver disease (vs normal 4g/day)",
        "valproic acid": "Hepatotoxic; contraindicated in severe liver disease",
        "statins": "Monitor LFTs; reduce dose or switch if ALT >3x ULN",
        "isoniazid": "High hepatotoxicity risk; monitor LFTs monthly",
        "rifampin": "Potent enzyme inducer; hepatotoxic",
        "fluconazole": "Reduce dose in hepatic impairment",
    }
    _RENAL_KEYWORDS = {"kidney", "renal", "ckd", "esrd", "dialysis", "nephro", "egfr"}
    _HEPATIC_KEYWORDS = {"liver", "hepatic", "cirrhosis", "hepatitis", "fatty liver", "nafld", "nash", "ast", "alt"}

    has_renal = any(kw in patient_context.lower() for kw in _RENAL_KEYWORDS)
    has_hepatic = any(kw in patient_context.lower() for kw in _HEPATIC_KEYWORDS)

    if has_renal:
        for med in patient_meds:
            for drug, warning in _RENAL_ADJUST_DRUGS.items():
                if drug in med.lower():
                    alerts.append(
                        f"🟡 RENAL DOSE WARNING: {med.title()} requires renal dose adjustment\n"
                        f"   {warning}"
                    )
    if has_hepatic:
        for med in patient_meds:
            for drug, warning in _HEPATIC_ADJUST_DRUGS.items():
                if drug in med.lower():
                    alerts.append(
                        f"🟡 HEPATIC DOSE WARNING: {med.title()} requires hepatic dose adjustment\n"
                        f"   {warning}"
                    )

    # --- 8. Age/Comorbidity – Beers Criteria (Elderly) ---
    _BEERS_CRITERIA = {
        "diphenhydramine": {"min_age": 65, "reason": "Strong anticholinergic — confusion, urinary retention, constipation risk", "severity": "major"},
        "diazepam": {"min_age": 65, "reason": "Long-acting benzodiazepine — falls, fractures, sedation", "severity": "major"},
        "lorazepam": {"min_age": 65, "reason": "Benzodiazepine — falls, cognitive impairment", "severity": "major"},
        "alprazolam": {"min_age": 65, "reason": "Benzodiazepine — falls, cognitive impairment", "severity": "major"},
        "amitriptyline": {"min_age": 65, "reason": "Tricyclic antidepressant — anticholinergic, sedation, orthostatic hypotension", "severity": "major"},
        "chlorpheniramine": {"min_age": 65, "reason": "First-gen antihistamine — anticholinergic, sedation", "severity": "moderate"},
        "promethazine": {"min_age": 65, "reason": "Anticholinergic + sedation risk", "severity": "major"},
        "meperidine": {"min_age": 65, "reason": "Neurotoxic metabolite accumulates — seizure risk", "severity": "major"},
        "indomethacin": {"min_age": 65, "reason": "Highest GI bleeding risk among NSAIDs in elderly", "severity": "major"},
        "glyburide": {"min_age": 65, "reason": "Long-acting sulfonylurea — prolonged hypoglycemia risk", "severity": "moderate"},
        "metoclopramide": {"min_age": 65, "reason": "Tardive dyskinesia risk increases with age", "severity": "moderate"},
        "nitrofurantoin": {"min_age": 65, "reason": "Ineffective if CrCl <30 (common in elderly); pulmonary toxicity", "severity": "moderate"},
    }
    # Try to extract age from patient context
    import re
    age_match = re.search(r'(?:age|aged?)[:\s]*(\d{1,3})', patient_context.lower())
    patient_age = int(age_match.group(1)) if age_match else None

    if patient_age and patient_age >= 65:
        for med in patient_meds:
            for drug, rule in _BEERS_CRITERIA.items():
                if drug in med.lower() and patient_age >= rule["min_age"]:
                    icon = "🔴" if rule["severity"] == "major" else "🟡"
                    alerts.append(
                        f"{icon} BEERS CRITERIA [{rule['severity'].upper()}]: "
                        f"{med.title()} is potentially inappropriate for patients age ≥{rule['min_age']}\n"
                        f"   Reason: {rule['reason']}"
                    )

    if not alerts and not treatment_info:
        return ""

    # Format output
    output = []
    if alerts:
        output.append("⚠️  DRUG SAFETY ALERTS (Deterministic — Knowledge Graph):")
        output.extend(alerts)

    if treatment_info:
        output.append("\n💊 GUIDELINE-BASED TREATMENTS (Knowledge Graph):")
        output.extend(treatment_info)

    return "\n".join(output)


def _extract_medication_names(patient_context: str) -> list:
    """
    Extract medication names from patient context string.
    Handles MIMIC format: "Active Medications:\\n- MedName (description)"
    """
    meds = []
    in_meds_section = False

    for line in patient_context.split('\n'):
        stripped = line.strip()

        # Detect medication section headers
        if 'medication' in stripped.lower() or 'active meds' in stripped.lower():
            in_meds_section = True
            continue

        # End of meds section: blank line after content, or new section header
        if in_meds_section and (stripped.startswith('===') or stripped.startswith('---')):
            in_meds_section = False
            continue

        # Only process bullet-point lines in the meds section
        if in_meds_section and stripped.startswith(('- ', '• ', '* ')):
            # Clean up: "- Aspirin (analgesic)" → "Aspirin"
            med_name = stripped.lstrip('-•* ').strip()

            # Remove parenthetical descriptions: "Aspirin (analgesic)" → "Aspirin"
            if '(' in med_name:
                med_name = med_name[:med_name.index('(')].strip()

            # Take first word (drug name), remove dosage suffixes
            parts = med_name.split()
            if parts:
                name = parts[0].rstrip(',;:')
                # Skip short/non-alpha tokens
                if len(name) > 2 and name[0].isalpha():
                    meds.append(name.lower())

    return list(set(meds))  # Deduplicate


def _extract_diagnosis_names(patient_context: str) -> list:
    """
    Extract diagnosis names from patient context string.
    Handles MIMIC format: "Diagnoses:\\n- Some Diagnosis (ICD: code)"
    """
    diagnoses = []
    in_diag_section = False

    for line in patient_context.split('\n'):
        stripped = line.strip()

        # Detect diagnosis section
        if 'diagnos' in stripped.lower() or 'active conditions' in stripped.lower():
            in_diag_section = True
            continue
        # End of section
        if in_diag_section and (stripped.startswith('===') or stripped.startswith('---')):
            in_diag_section = False
            continue
        # New section detected (e.g., "Active Medications:")
        if in_diag_section and stripped and not stripped.startswith(('- ', '• ', '* ')) and ':' in stripped:
            in_diag_section = False
            continue

        if stripped.startswith(('- ', '• ', '* ')) and in_diag_section:
            diag = stripped.lstrip('-•* ').strip()
            # Remove ICD codes if present (e.g., "(ICD: J18.9)")
            if '(' in diag:
                diag = diag[:diag.index('(')].strip()
            # Remove common suffixes and comma-separated qualifiers
            diag = diag.replace(' NOS', '').replace(', UNSPECIFIED', '').replace(' UNSPECIFIED', '')
            # Clean up comma artifacts: "Pneumonia,organism" → "Pneumonia"
            if ',' in diag:
                diag = diag.split(',')[0].strip()
            if len(diag) > 3:
                diagnoses.append(diag.lower())

    return diagnoses


# =============================================================================
# Hybrid Orchestrator
# =============================================================================

SYNTHESIS_PROMPT = """You are TrustMed AI, a Neuro-Symbolic Clinical Decision Support System.

You synthesize FIVE knowledge streams to provide comprehensive medical insights:

1. PATIENT CONTEXT: Real-time vitals, diagnoses, and medications
2. UPLOADED REPORTS: Structured summaries extracted from newly uploaded patient PDF reports
3. KNOWLEDGE GRAPH: Verified medical facts (diseases, symptoms, precautions)
4. MEDICAL LITERATURE: Semantic search over clinical documents
5. MULTIMODAL IMAGING REPORT: Vision analysis + Text guidelines + Similar historical cases

CRITICAL INSTRUCTIONS:
- **CONVERSATION CONTINUITY**: The CONVERSATION HISTORY below contains ALL previous exchanges
  in this session. If the user previously uploaded an image and you analyzed it, those findings
  are in the history. For follow-up questions (e.g., "is there pneumonia?", "what about the lungs?"),
  you MUST refer back to your previous analysis in the conversation history. DO NOT say "no imaging
  data provided" if you already analyzed an image in an earlier turn.
- For FOLLOW-UP questions: re-read your previous ASSISTANT responses in the history carefully,
  then answer the new question based on findings you already reported.
- When an image is provided in the CURRENT turn, the MULTIMODAL IMAGING REPORT contains:
  * Visual findings from AI analysis (tagged with confidence: [HIGH] or [LOW])
  * Retrieved medical guidelines (Text-RAG, reranked by relevance)
  * Similar historical cases (Visual-RAG, with ground-truth labels)
- **CONFIDENCE HIERARCHY**: Only cite [HIGH] confidence findings as definitive.
  Treat [LOW] findings as uncertain possibilities requiring further investigation.
  If output is marked [UNSTRUCTURED], treat ALL findings as LOW confidence.
- **VISUAL-RAG PRIORITY**: If Visual-RAG ground-truth labels contradict the vision model's
  findings, TRUST Visual-RAG. Historical cases with verified labels are more reliable than
  AI vision model interpretations.
- **CROSS-REFERENCE VALIDATION**: The MULTIMODAL IMAGING REPORT may contain a
  "🔗 CROSS-REFERENCE VALIDATION" section that compares vision model findings against
  ground-truth labels from similar MIMIC-CXR cases. If present:
  * ✅ CORROBORATED findings should be presented with higher confidence
  * ⚠ NOT CORROBORATED findings should be presented cautiously as possibilities
  * 🔍 POTENTIALLY MISSED conditions should be mentioned as worth investigating
  You MUST include these cross-reference results in your output under a dedicated section.
- When NO image is provided but history contains image analysis, USE that prior analysis.
- When UPLOADED REPORTS are available, treat them as supplemental patient evidence from
  patient-uploaded files. Clearly label report-derived facts as coming from uploaded reports,
  especially if they differ from chart-derived data.
- Integrate ALL sources to form a complete clinical picture.
- If Knowledge Graph contradicts Literature, PRIORITIZE the Knowledge Graph.
- Cite sources naturally: "The imaging suggests...", "Based on similar cases..."
- Flag drug interactions or concerning findings.
- **DRUG SAFETY ALERTS**: If the KNOWLEDGE GRAPH section contains "DRUG INTERACTION" or
  "CONTRAINDICATION" alerts, these are DETERMINISTIC findings from structured graph traversal
  (not LLM-generated). You MUST prominently include these alerts under a dedicated
  "⚠️ Drug Safety" section. These are factual and should never be omitted or downplayed.

WRITING STYLE — THIS IS CRITICAL:
- Write as a **senior physician explaining to a colleague** — warm, professional, clear.
- Use **flowing prose**, not robotic bullet-point dumps. Weave findings into a narrative.
- **NEVER** expose raw internal tags like [HIGH], [LOW], [UNSTRUCTURED] to the user.
  Instead, convey confidence naturally: "clearly shows", "likely indicates", "a subtle finding
  that may suggest", "warrants further evaluation".
- Use markdown formatting: **bold** for key findings, headers for sections, and occasional
  bullet points only when listing distinct items (e.g., differential diagnoses or next steps).
- Keep it **concise but thorough** — avoid repeating the same finding in multiple sections.
- Sound knowledgeable and empathetic, not like a form or checklist.

OUTPUT FORMAT (when image provided or referenced from history):

## 🩺 Clinical Assessment
A concise narrative integrating the key visual findings with the patient's clinical context.
Explain WHAT you see and WHY it matters clinically, in 2-3 sentences.

## 🔬 Imaging Findings
Describe the image findings in natural language. Mention the modality and region.
Note similar historical cases and what they confirm or challenge.
Clearly distinguish confident findings from uncertain ones using natural language.

## 🔗 Evidence Cross-Reference
If cross-reference validation data is available in the MULTIMODAL IMAGING REPORT,
include this section. Report which findings are corroborated by labeled similar cases
and which are not. Mention the number of similar cases used. If any conditions were
detected in similar cases but not reported by the vision model, note them here.
If no cross-reference data is available, OMIT this section entirely.

## 📋 Clinical Correlation
Reference relevant medical guidelines and knowledge graph facts.
Explain how the findings connect to possible diagnoses. Include differential diagnoses
if appropriate.

## ✅ Recommended Next Steps
Actionable, prioritized recommendations — what to do first and why.
Include relevant follow-up tests, monitoring, and safety considerations.

If DRUG SAFETY ALERTS exist, add:
## ⚠️ Drug Safety
Prominently list any drug interactions or contraindications.

OUTPUT FORMAT (for follow-up questions):
- Answer the specific question **directly** in a conversational tone.
- Reference your prior analysis naturally — don't repeat everything.
- Keep it focused and helpful.

---
CONVERSATION HISTORY (previous exchanges in this session — USE THIS for follow-ups):
{chat_history}
---
{patient_context}
---
UPLOADED REPORTS:
{report_context}
---
KNOWLEDGE GRAPH FACTS (includes drug safety alerts if detected):
{graph_context}
---
MEDICAL LITERATURE:
{vector_context}
---
MULTIMODAL IMAGING REPORT (current turn only — if "No image provided", check history above):
{vision_context}
---

User Query: {query}

Response:"""


SAFETY_CRITIC_PROMPT = """You are an INDEPENDENT Medical Safety Reviewer. You are a DIFFERENT model from the one that wrote the draft below. Your job is adversarial: find errors the original model would miss.

=== CONTEXT ===
{context}

=== USER QUERY ===
{query}

=== DRAFT RESPONSE TO REVIEW ===
{draft}

=== YOUR REVIEW CHECKLIST ===
1. DOSAGE SAFETY: Are any drug dosages mentioned? If so, are they within safe ranges?
2. DRUG INTERACTIONS: Does the draft miss any interactions between the patient's current medications?
3. CONTRAINDICATIONS: Does the draft recommend anything contraindicated by the patient's conditions or vitals?
4. HALLUCINATION CHECK: Compare the draft's claims against the provided context. Flag any claims NOT supported by the context.
5. VISION vs VISUAL-RAG: If Visual-RAG historical cases (high similarity) suggest diagnosis X, but the draft says something completely different, the draft is WRONG — Visual-RAG evidence takes priority.
6. OMISSION CHECK: Are there critical findings in the context that the draft fails to mention?

=== OUTPUT FORMAT (strict) ===
You MUST respond in this exact format:

VERDICT: SAFE or UNSAFE
ISSUES:
- [list each issue found, or "None" if safe]
CORRECTIONS:
- [specific corrections needed, or "None" if safe]

If VERDICT is UNSAFE, also add:
CORRECTED_RESPONSE:
[full corrected response here]

Review:"""


SOAP_NOTE_PROMPT = """You are an expert clinical documentation specialist. Generate a professional SOAP note from the following conversation between a medical AI assistant and a user.

Patient Context: {patient_context}
Imaging/Lab Context: {vision_context}

Conversation History:
{history}

INSTRUCTIONS:
1. Analyze the entire conversation history carefully
2. Extract all clinically relevant information
3. Return a JSON object with exactly this structure (no markdown, no code fences, pure JSON):

{{
  "subjective": {{
    "chief_complaint": "Primary reason for consultation",
    "history_of_present_illness": "Detailed narrative of the presenting issue",
    "symptoms": ["symptom1", "symptom2"],
    "relevant_history": "Any past medical/surgical/family history mentioned"
  }},
  "objective": {{
    "vitals": "Any vitals or measurements mentioned, or 'Not provided'",
    "physical_findings": "Physical examination findings if any",
    "imaging_results": "Imaging or lab results discussed",
    "clinical_observations": "Other objective clinical data"
  }},
  "assessment": {{
    "primary_diagnosis": "Most likely diagnosis discussed",
    "differential_diagnoses": ["differential1", "differential2"],
    "clinical_reasoning": "Brief reasoning for the assessment",
    "severity": "Mild/Moderate/Severe if determinable"
  }},
  "plan": {{
    "medications": ["medication1 with dosage if discussed"],
    "lifestyle_modifications": ["recommendation1", "recommendation2"],
    "follow_up": "Follow-up recommendations",
    "patient_education": "Key points discussed with patient",
    "referrals": "Any specialist referrals suggested"
  }}
}}

IMPORTANT:
- Extract ONLY information actually discussed in the conversation
- Do not fabricate vital signs or findings not mentioned
- If a field has no data from the conversation, use "Not discussed" or an empty array
- Keep entries concise and professional
- Output ONLY valid JSON, no other text
"""


def _extract_medical_terms_for_graph(
    clean_query: str,
    vision_result: str = "",
    patient_context: str = "",
    report_context: str = ""
) -> str:
    """
    Extract medical terms from available context to form a smart Knowledge Graph query.

    The raw user query often contains non-medical tokens ("assess", "analyse", "chest xray")
    that cause the Cypher generator to search for nonsense like Disease.name CONTAINS "chest xray".

    This function extracts actual medical conditions from:
    1. Vision findings ([HIGH] and [LOW] tagged findings)
    2. Patient diagnoses (from MIMIC data)
    3. Uploaded report findings and diagnoses
    4. The user query itself (stripping common non-medical words)

    Args:
        clean_query: User query with image attachment tags removed
        vision_result: Full vision agent output (may contain findings)
        patient_context: Patient context string (may contain diagnoses)
        report_context: Uploaded report digest string (may contain findings/diagnoses)

    Returns:
        A focused medical query string suitable for Knowledge Graph search
    """
    medical_terms = []

    # 1. Extract from vision findings (most specific)
    if vision_result and "No image provided" not in vision_result:
        for line in vision_result.split('\n'):
            stripped = line.strip()
            # High-confidence findings
            if stripped.startswith("[HIGH]"):
                finding = stripped.replace("[HIGH]", "").strip()
                # Extract key medical words (skip generic descriptors)
                medical_terms.append(finding)
            # Ground-truth labels from Visual-RAG
            elif stripped.startswith("Ground-Truth Label:"):
                label = stripped.replace("Ground-Truth Label:", "").strip()
                if label:
                    medical_terms.append(label)
            # Overall impression
            elif stripped.startswith("Overall Impression:"):
                impression = stripped.replace("Overall Impression:", "").strip()
                medical_terms.append(impression)

    # 2. Extract diagnosed conditions from patient context
    if patient_context and "No patient-specific" not in patient_context:
        for line in patient_context.split('\n'):
            stripped = line.strip()
            # Look for diagnosis lines (from MIMIC format: "- DIAGNOSIS_NAME")
            if stripped.startswith("- ") and any(c.isupper() for c in stripped):
                diagnosis = stripped.lstrip("- ").strip()
                # Skip generic codes, keep disease names
                if len(diagnosis) > 3 and not diagnosis.startswith("V") and not diagnosis[0].isdigit():
                    medical_terms.append(diagnosis)

    # 3. Extract diagnoses and findings from uploaded report context
    if report_context and "No uploaded patient reports provided." not in report_context:
        current_section = None
        for line in report_context.split('\n'):
            stripped = line.strip()
            lowered = stripped.lower()

            if lowered.startswith("diagnoses:"):
                current_section = "diagnoses"
                continue
            if lowered.startswith("findings:"):
                current_section = "findings"
                continue
            if current_section and stripped.startswith(('- ', '• ', '* ')):
                medical_terms.append(stripped.lstrip('-•* ').strip())
                continue
            if current_section and stripped and not stripped.startswith(('- ', '• ', '* ')):
                current_section = None

    # 4. Extract from user query (strip non-medical stop words)
    stop_words = {
        'assess', 'analyze', 'analyse', 'patient', 'check', 'look', 'tell',
        'show', 'find', 'what', 'this', 'that', 'with', 'from', 'about',
        'image', 'scan', 'xray', 'x-ray', 'chest', 'photo', 'picture',
        'upload', 'attachment', 'please', 'help', 'need', 'want', 'could',
        'would', 'should', 'does', 'have', 'there', 'signs', 'any', 'are',
        'the', 'and', 'for', 'can', 'you', 'see'
    }
    query_words = clean_query.lower().split()
    query_medical = [w for w in query_words if w not in stop_words and len(w) > 2 and not w.isdigit()]
    if query_medical:
        medical_terms.append(" ".join(query_medical))

    if not medical_terms:
        return clean_query  # Fallback to original query

    # Combine and deduplicate while preserving order
    seen = set()
    unique_terms = []
    for term in medical_terms:
        lower = term.lower().strip()
        if lower not in seen and lower:
            seen.add(lower)
            unique_terms.append(term.strip())

    # Join into a focused query (limit to avoid overly long Cypher)
    result = ". ".join(unique_terms[:5])
    return result[:500]


def _check_visual_rag_consistency(vision_result: str, draft_response: str) -> str:
    """
    Deterministic (non-LLM) safety check for vision hallucinations.

    Parses the vision agent output to compare:
    - What the vision model found (HIGH-CONFIDENCE findings)
    - What Visual-RAG historical cases show (Ground-Truth Labels)

    If 2+ historical cases consistently show a specific pathology (e.g., PNEUMONIA)
    but the vision model found something completely unrelated (e.g., "shoulder dislocation"),
    this function returns a corrected response that trusts Visual-RAG over the vision model.

    Args:
        vision_result: Full output from vision agent (contains both vision findings and Visual-RAG)
        draft_response: The draft LLM synthesis response

    Returns:
        Corrected response string if hallucination detected, or empty string if consistent
    """
    if not vision_result or "No image provided" in vision_result:
        return ""

    # Extract Visual-RAG ground-truth labels
    visual_rag_labels = []
    visual_rag_similarities = []
    lines = vision_result.split('\n')
    for line in lines:
        stripped = line.strip()
        if stripped.startswith("Ground-Truth Label:"):
            label = stripped.replace("Ground-Truth Label:", "").strip().upper()
            if label:
                visual_rag_labels.append(label)
        if "Similarity:" in stripped:
            try:
                sim_str = stripped.split("Similarity:")[1].strip().rstrip('%')
                sim_val = float(sim_str) / 100 if float(sim_str) > 1 else float(sim_str)
                visual_rag_similarities.append(sim_val)
            except (ValueError, IndexError):
                pass

    if len(visual_rag_labels) < 2:
        # Not enough Visual-RAG evidence to override
        return ""

    # Check if Visual-RAG labels are consistent (2+ agree on same diagnosis)
    from collections import Counter
    label_counts = Counter(visual_rag_labels)
    dominant_label, dominant_count = label_counts.most_common(1)[0]

    if dominant_count < 2:
        # No consistent signal from Visual-RAG
        return ""

    # Check average similarity of dominant label matches
    avg_similarity = sum(visual_rag_similarities) / len(visual_rag_similarities) if visual_rag_similarities else 0
    if avg_similarity < 0.75:
        # Similarity too low to override
        return ""

    # Extract vision model's high-confidence findings
    vision_findings = []
    in_high_confidence = False
    for line in lines:
        stripped = line.strip()
        if "HIGH-CONFIDENCE" in stripped:
            in_high_confidence = True
            continue
        if "UNCERTAIN" in stripped or "Cannot Assess" in stripped:
            in_high_confidence = False
        if in_high_confidence and stripped.startswith("[HIGH]"):
            finding = stripped.replace("[HIGH]", "").strip().upper()
            vision_findings.append(finding)

    # Check for contradiction: vision findings don't mention the dominant Visual-RAG label
    dominant_keywords = dominant_label.lower().split()
    draft_lower = draft_response.lower()
    vision_text_lower = " ".join(vision_findings).lower()

    # If the dominant Visual-RAG diagnosis is already in the draft, no override needed
    if any(kw in draft_lower for kw in dominant_keywords if len(kw) > 3):
        return ""

    # If vision findings exist but don't mention Visual-RAG's diagnosis at all
    if vision_findings and not any(kw in vision_text_lower for kw in dominant_keywords if len(kw) > 3):
        # HALLUCINATION DETECTED: Vision says something different from Visual-RAG
        override = (
            f"[SAFETY OVERRIDE — Vision Hallucination Detected]\n\n"
            f"The AI vision model's findings were inconsistent with historical case evidence. "
            f"Based on Visual-RAG analysis, {dominant_count} out of {len(visual_rag_labels)} "
            f"similar historical cases (average similarity: {avg_similarity:.0%}) are labeled as "
            f"**{dominant_label}**.\n\n"
            f"The vision model's original findings have been flagged as potentially hallucinated. "
            f"Clinical assessment should be based on the Visual-RAG evidence:\n\n"
            f"**Most Likely Diagnosis (based on similar cases):** {dominant_label}\n"
            f"**Evidence Strength:** {dominant_count}/{len(visual_rag_labels)} similar cases agree\n"
            f"**Average Similarity:** {avg_similarity:.0%}\n\n"
            f"**Recommendation:** Correlate with clinical presentation and consider appropriate "
            f"diagnostic workup for {dominant_label.lower()}. The AI vision model's original "
            f"interpretation should be disregarded in favor of evidence-based assessment.\n\n"
            f"[SAFETY NOTE: This response was automatically corrected by the deterministic "
            f"hallucination detector. The vision model's findings contradicted {dominant_count} "
            f"historical cases with high similarity scores.]"
        )
        return override

    return ""


async def ask_trustmed(
    query: str,
    chat_history: list = None,
    temperature: float = None,
    model: str = None,
    vision_model: str = None,
    patient_id: str = None,
    report_context: str = "",
) -> str:
    """
    Main orchestrator - combines all knowledge sources to answer medical queries.
    
    Args:
        query: User's medical question
        chat_history: List of previous messages [{"role": "user/assistant", "content": "..."}]
        temperature: LLM temperature override (0.0–1.0). Defaults to 0.1.
        model: OpenRouter model ID override. Defaults to OPENROUTER_MODEL env var.
        vision_model: Vision model ID override. Defaults to first in VISION_MODELS list.
        
    Returns:
        Comprehensive AI-generated response
    """
    print("\n" + "=" * 70)
    print("🧠 TRUSTMED BRAIN - Processing Query")
    print("=" * 70)
    print(f"Query: {query}")
    
    # Check for image attachments - Use full Vision Agent
    image_match = re.search(IMAGE_ATTACHMENT_PATTERN, query)
    if image_match:
        image_path = image_match.group(1)
        print(f"\n👁️ Step 0: Engaging Vision Agent on {image_path}...")
        print(f"   (Vision + Visual RAG — text-RAG deferred to Step C)")
        try:
            # Set user's preferred vision model (if any)
            if vision_model:
                set_preferred_vision_model(vision_model)
                print(f"   👁️ Preferred vision model: {vision_model}")
            # Skip vision agent's text-RAG since the brain does broader 3-collection search
            set_skip_text_rag(True)
            # This triggers the multimodal pipeline:
            # 1. Compound figure detection (auto-splits multi-panel images)
            # 2. Vision analysis (LLaVA/Gemini) — per-panel if compound
            # 3. Visual RAG (similar historical cases)
            # Text RAG is handled by Step C with all 3 collections + reranking
            vision_result = analyze_with_compound_support.invoke(image_path)
            set_skip_text_rag(False)  # Reset flag
            set_preferred_vision_model(None)  # Reset vision model
            cache_info = get_vision_cache_stats()
            print(f"  ✓ Vision Agent complete: {len(vision_result)} chars "
                  f"(cache: {cache_info['cached_images']}/{cache_info['max_size']} images, "
                  f"hit rate: {cache_info['hit_rate']})")
        except Exception as e:
            set_skip_text_rag(False)  # Reset flag on error
            set_preferred_vision_model(None)  # Reset vision model on error
            vision_result = f"Error in Vision Agent: {str(e)}"
            print(f"  ✗ Vision Agent failed: {e}")
        # Clean the query by removing the attachment tag
        clean_query = query.replace(image_match.group(0), '').strip()
    else:
        vision_result = "No image provided."
        clean_query = query
    
    # Format chat history — preserve enough context for follow-up questions
    if chat_history and len(chat_history) > 0:
        history_parts = []
        recent_messages = chat_history[-10:]  # Last 10 messages (5 exchanges)
        for msg in recent_messages:
            role = msg['role'].upper()
            content = msg['content']
            # Keep last assistant message in full (contains clinical findings)
            # Truncate older messages more aggressively
            if msg == recent_messages[-1] or msg == recent_messages[-2]:
                # Last exchange: keep full content (up to 2000 chars)
                if len(content) > 2000:
                    content = content[:2000] + "\n[...truncated...]"
            else:
                # Older messages: moderate truncation
                if len(content) > 800:
                    content = content[:800] + "\n[...truncated...]"
            history_parts.append(f"{role}: {content}")
        history_text = "\n\n".join(history_parts)
        print(f"\n📜 Including {len(recent_messages)} messages from history")
    else:
        history_text = "No previous conversation."
        print("\n📜 No conversation history")
    
    # Step A: Patient Context (synchronous, fast)
    print("📋 Step A: Fetching Patient Context...")
    patient_context = get_patient_context(clean_query, patient_id)
    if patient_context:
        print("  ✓ Patient data retrieved")
    else:
        print("  ⚠ No patient ID detected in query")
        patient_context = "No patient-specific data requested."
    report_context = (report_context or "").strip()
    if report_context:
        print("  ✓ Uploaded patient report context retrieved")
    else:
        report_context = "No uploaded patient reports provided."

    # Build smart query for Knowledge Graph using vision findings + patient diagnoses
    graph_query = _extract_medical_terms_for_graph(clean_query, vision_result, patient_context, report_context)
    print(f"🔍 Smart Graph Query: {graph_query[:100]}...")

    # Build enriched vector search query: combine user query with vision findings
    vector_query = clean_query
    if vision_result and "No image provided" not in vision_result:
        # Append high-confidence findings to vector search for better retrieval
        vision_terms = []
        for line in vision_result.split('\n'):
            stripped = line.strip()
            if stripped.startswith("[HIGH]"):
                vision_terms.append(stripped.replace("[HIGH]", "").strip())
        if vision_terms:
            vector_query = f"{clean_query} {' '.join(vision_terms[:3])}"

    # Steps B & C: Run Graph Search and Vector Search IN PARALLEL
    print("🔗📚 Steps B+C: Querying Knowledge Graph & Medical Literature (parallel)...")
    try:
        graph_task = asyncio.wait_for(
            asyncio.to_thread(get_graph_context, graph_query, model),
            timeout=30.0  # 30s hard timeout for graph chain (LLM + Neo4j)
        )
        vector_task = asyncio.to_thread(get_vector_context, vector_query)
        graph_context, vector_context = await asyncio.gather(
            graph_task, vector_task, return_exceptions=True
        )
        # Handle graph timeout/errors gracefully
        if isinstance(graph_context, Exception):
            print(f"  ⚠️ Graph query failed: {graph_context}")
            graph_context = "No structured data found."
        if isinstance(vector_context, Exception):
            print(f"  ⚠️ Vector search failed: {vector_context}")
            vector_context = "No relevant literature found."
    except Exception as e:
        print(f"  ⚠️ Parallel search error: {e}")
        graph_context = "No structured data found."
        vector_context = "No relevant literature found."
    print(f"  ✓ Graph context: {len(graph_context)} chars")
    print(f"  ✓ Vector context: {len(vector_context)} chars")

    # Step B2: Deterministic Drug Interaction Check (No LLM — pure graph traversal)
    drug_safety_alerts = ""
    combined_patient_context = "\n\n".join(
        part for part in (patient_context, report_context)
        if part and "No uploaded patient reports provided." not in part
    )
    has_structured_patient_context = (
        (patient_context and "No patient-specific" not in patient_context)
        or (report_context and "No uploaded patient reports provided." not in report_context)
    )
    if combined_patient_context and has_structured_patient_context:
        print("💊 Step B2: Checking Drug Interactions (deterministic)...")
        try:
            drug_safety_alerts = await asyncio.wait_for(
                asyncio.to_thread(check_drug_interactions, combined_patient_context),
                timeout=15.0  # 15-second hard timeout
            )
            if drug_safety_alerts:
                alert_count = drug_safety_alerts.count("DRUG INTERACTION") + drug_safety_alerts.count("CONTRAINDICATION")
                print(f"  ⚠️ Found {alert_count} drug safety alerts!")
            else:
                print("  ✓ No drug interactions or contraindications detected")
        except asyncio.TimeoutError:
            print("  ⚠️ Drug interaction check timed out (15s) — skipping")
            drug_safety_alerts = ""
        except Exception as e:
            print(f"  ⚠️ Drug interaction check failed: {e}")
            drug_safety_alerts = ""

    # Step D: Construct final prompt
    print("💡 Step D: Synthesizing Response...")

    # Inject drug safety alerts into graph context if found
    enriched_graph_context = graph_context
    if drug_safety_alerts:
        enriched_graph_context = f"{graph_context}\n\n{drug_safety_alerts}"

    final_prompt = SYNTHESIS_PROMPT.format(
        chat_history=history_text,
        patient_context=patient_context,
        report_context=report_context,
        graph_context=enriched_graph_context,
        vector_context=vector_context,
        vision_context=vision_result,
        query=clean_query
    )
    
    # Step E: Generate final response
    synthesis_temp = temperature if temperature is not None else 0.1
    synthesis_model = model if model else OPENROUTER_MODEL
    print(f"🌡️ Using temperature: {synthesis_temp}")
    print(f"🤖 Using model: {synthesis_model}")

    if synthesis_model.startswith("vertex/"):
        # Route to MedGemma on Vertex AI
        print("  🧬 Routing to MedGemma 27B (Vertex AI) for text synthesis...")
        draft_response = call_medgemma_text(
            final_prompt, temperature=synthesis_temp, max_tokens=2000
        )
    else:
        llm = ChatOpenAI(
            model=synthesis_model,
            openai_api_key=OPENROUTER_API_KEY,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=synthesis_temp
        )
        response = llm.invoke(final_prompt)
        draft_response = response.content

    # Step F: Deterministic Safety Check (Non-LLM, runs first)
    print("🛡️ Step F: Running Safety Checks...")

    # F.1: Deterministic Visual-RAG Consistency Check
    # Catches the primary hallucination pattern: vision says X but historical cases say Y
    deterministic_override = _check_visual_rag_consistency(vision_result, draft_response)
    if deterministic_override:
        print("  ⚠️ DETERMINISTIC OVERRIDE: Visual-RAG contradicts vision model!")
        draft_response = deterministic_override

    # F.2: Independent LLM Safety Critic (DIFFERENT model from synthesizer)
    # This ensures the critic has genuinely different failure modes
    safety_context = f"""Patient Context: {patient_context}

Uploaded Reports:
{report_context}

Knowledge Graph: {enriched_graph_context}

Vision Analysis & Similar Cases (REVIEW FOR DISCREPANCIES):
{vision_result}
"""
    safety_prompt = SAFETY_CRITIC_PROMPT.format(
        context=safety_context,
        query=clean_query,
        draft=draft_response
    )

    # Independent critic: different model + different temperature = real adversarial review
    # Uses retry with fallback models to handle 429 rate limits on free tiers
    critic_models = [SAFETY_CRITIC_MODEL] + SAFETY_CRITIC_FALLBACKS
    print(f"  🔍 Safety critic model: {SAFETY_CRITIC_MODEL} (independent from {OPENROUTER_MODEL})")

    def _make_critic(model_name):
        return ChatOpenAI(
            model=model_name or SAFETY_CRITIC_MODEL,
            openai_api_key=OPENROUTER_API_KEY,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=SAFETY_CRITIC_TEMPERATURE
        )

    try:
        critique_text = await asyncio.wait_for(
            asyncio.to_thread(
                lambda: _invoke_with_retry(_make_critic, safety_prompt, max_retries=2, models=critic_models)
            ),
            timeout=45.0  # 45s to allow retries
        )

        # Parse structured verdict
        verdict_safe = "VERDICT: SAFE" in critique_text.upper()
        verdict_unsafe = "VERDICT: UNSAFE" in critique_text.upper()

        if verdict_unsafe and "CORRECTED_RESPONSE:" in critique_text:
            # Extract the corrected response
            corrected = critique_text.split("CORRECTED_RESPONSE:", 1)[1].strip()
            if len(corrected) > 100:  # Sanity check: correction must be substantial
                final_answer = corrected
                # Extract and display the issues found
                if "ISSUES:" in critique_text:
                    issues_section = critique_text.split("ISSUES:", 1)[1]
                    if "CORRECTIONS:" in issues_section:
                        issues_section = issues_section.split("CORRECTIONS:", 1)[0]
                    print(f"  ⚠️ Safety critic found issues:\n{issues_section.strip()}")
                print("  ⚠️ Safety Layer OVERRODE the response!")
            else:
                final_answer = draft_response
                print("  ✓ Safety critic flagged UNSAFE but correction was too short — keeping draft")
        elif verdict_safe:
            final_answer = draft_response
            print("  ✓ Safety critic: SAFE (independent review passed)")
        else:
            # Ambiguous verdict — log but keep draft (conservative approach)
            final_answer = draft_response
            print(f"  ⚠️ Safety critic returned ambiguous verdict — keeping draft")
            if "ISSUES:" in critique_text:
                issues_section = critique_text.split("ISSUES:", 1)[1]
                if "CORRECTIONS:" in issues_section:
                    issues_section = issues_section.split("CORRECTIONS:", 1)[0]
                print(f"     Notes: {issues_section.strip()[:200]}")

    except asyncio.TimeoutError:
        final_answer = draft_response
        print("  ⚠️ Safety critic timed out (45s) — keeping draft")
    except Exception as e:
        final_answer = draft_response
        print(f"  ⚠️ Safety critic error: {e} — keeping draft")
    
    print("\n" + "=" * 70)
    print("🩺 TRUSTMED AI RESPONSE")
    print("=" * 70)
    print(final_answer)
    
    return final_answer

async def ask_trustmed_direct(query: str, model: str = None) -> str:
    """
    Fast-path LLM call that bypasses all RAG (Neo4j, ChromaDB, Safety Critic).
    Useful for dictionary-style explanations where no patient context or clinical literature is needed.
    """
    import aiohttp
    
    request_model = model or OPENROUTER_MODEL
    headers = {
        "Authorization": f"Bearer {OPENROUTER_API_KEY}",
        "Content-Type": "application/json"
    }
    payload = {
        "model": request_model,
        "messages": [{"role": "user", "content": query}]
    }

    try:
        timeout = aiohttp.ClientTimeout(total=20)
        connector = aiohttp.TCPConnector(ssl=get_ssl_context())
        async with aiohttp.ClientSession(timeout=timeout, connector=connector) as session:
            async with session.post(
                "https://openrouter.ai/api/v1/chat/completions",
                headers=headers,
                json=payload,
            ) as response:
                if response.status != 200:
                    error_text = await response.text()
                    raise Exception(f"OpenRouter API returned {response.status}: {error_text}")
                
                result = await response.json()
                if "choices" in result and len(result["choices"]) > 0:
                    return result["choices"][0]["message"]["content"]
                raise Exception("No choices in response")
    except Exception as e:
        print(f"Direct LLM call failed: {e}")
        return "Explanation unavailable. Please consult your physician."

async def ask_trustmed_streaming(query: str, chat_history: list = None,
                                  temperature: float = None, model: str = None,
                                  vision_model: str = None, patient_id: str = None,
                                  report_context: str = ""):
    """
    Streaming version of ask_trustmed — yields SSE event dicts.

    Event types:
        progress  — pipeline step update   {"type":"progress", "step":"...", "message":"..."}
        token     — LLM synthesis chunk    {"type":"token", "content":"..."}
        replace   — safety critic override {"type":"replace", "content":"..."}
        done      — pipeline complete      {"type":"done"}
        error     — fatal error            {"type":"error", "message":"..."}
    """
    try:
        print("🧠 TRUSTMED BRAIN (STREAMING) - Processing Query")
        print("=" * 70)
        print(f"Query: {query}")

        # ── Step 0: Vision Agent ─────────────────────────────────────────
        image_match = re.search(IMAGE_ATTACHMENT_PATTERN, query)
        if image_match:
            image_path = image_match.group(1)
            yield {"type": "progress", "step": "vision", "message": "👁️ Analyzing medical image…"}
            try:
                if vision_model:
                    set_preferred_vision_model(vision_model)
                set_skip_text_rag(True)
                vision_result = analyze_with_compound_support.invoke(image_path)
                set_skip_text_rag(False)
                set_preferred_vision_model(None)
                cache_info = get_vision_cache_stats()
                print(f"  ✓ Vision Agent complete: {len(vision_result)} chars "
                      f"(cache: {cache_info['cached_images']}/{cache_info['max_size']} images, "
                      f"hit rate: {cache_info['hit_rate']})")
            except Exception as e:
                set_skip_text_rag(False)
                set_preferred_vision_model(None)
                vision_result = f"Error in Vision Agent: {str(e)}"
                print(f"  ✗ Vision Agent failed: {e}")
            clean_query = query.replace(image_match.group(0), '').strip()
        else:
            vision_result = "No image provided."
            clean_query = query

        # ── Format chat history ──────────────────────────────────────────
        if chat_history and len(chat_history) > 0:
            history_parts = []
            recent_messages = chat_history[-10:]
            for msg in recent_messages:
                role = msg['role'].upper()
                content = msg['content']
                if msg == recent_messages[-1] or msg == recent_messages[-2]:
                    if len(content) > 2000:
                        content = content[:2000] + "\n[...truncated...]"
                else:
                    if len(content) > 800:
                        content = content[:800] + "\n[...truncated...]"
                history_parts.append(f"{role}: {content}")
            history_text = "\n\n".join(history_parts)
        else:
            history_text = "No previous conversation."

        # ── Step A: Patient Context ──────────────────────────────────────
        yield {"type": "progress", "step": "patient", "message": "📋 Retrieving patient context…"}
        resolved_patient_id = str(patient_id).strip() if patient_id else None
        patient_context = get_patient_context(clean_query, resolved_patient_id)
        if not patient_context:
            patient_context = "No patient-specific data requested."
        if not resolved_patient_id:
            import re as _re
            _pid_match = _re.search(r'\b(\d{7,8})\b', clean_query)
            if _pid_match:
                resolved_patient_id = _pid_match.group(1)
        if resolved_patient_id:
            yield {"type": "patient_context", "patient_id": resolved_patient_id}

        report_context = (report_context or "").strip()
        if not report_context:
            report_context = "No uploaded patient reports provided."

        graph_query = _extract_medical_terms_for_graph(clean_query, vision_result, patient_context, report_context)
        diagnosis_names = _extract_diagnosis_names(patient_context) if patient_context else []
        graph_source = "query"
        if diagnosis_names and any(diag in graph_query.lower() for diag in diagnosis_names):
            graph_source = "patient_diagnosis"
        yield {
            "type": "graph_context",
            "search_term": graph_query,
            "patient_id": resolved_patient_id,
            "source": graph_source,
        }

        vector_query = clean_query
        if vision_result and "No image provided" not in vision_result:
            vision_terms = []
            for line in vision_result.split('\n'):
                stripped = line.strip()
                if stripped.startswith("[HIGH]"):
                    vision_terms.append(stripped.replace("[HIGH]", "").strip())
            if vision_terms:
                vector_query = f"{clean_query} {' '.join(vision_terms[:3])}"

        # ── Steps B+C: Graph + Vector Search (parallel) ──────────────────
        yield {"type": "progress", "step": "search", "message": "🔗 Searching knowledge graph & medical literature…"}
        try:
            graph_task = asyncio.wait_for(
                asyncio.to_thread(get_graph_context, graph_query, model),
                timeout=30.0
            )
            vector_task = asyncio.wait_for(
                asyncio.to_thread(get_vector_context_fast, vector_query),
                timeout=12.0
            )
            graph_context, vector_context = await asyncio.gather(
                graph_task, vector_task, return_exceptions=True
            )
            if isinstance(graph_context, Exception):
                graph_context = "No structured data found."
            if isinstance(vector_context, Exception):
                vector_context = "No relevant literature found."
        except Exception:
            graph_context = "No structured data found."
            vector_context = "No relevant literature found."

        # ── Step B2: Drug Interaction Check ───────────────────────────────
        drug_safety_alerts = ""
        combined_patient_context = "\n\n".join(
            part for part in (patient_context, report_context)
            if part and "No uploaded patient reports provided." not in part
        )
        has_structured_patient_context = (
            (patient_context and "No patient-specific" not in patient_context)
            or (report_context and "No uploaded patient reports provided." not in report_context)
        )
        if combined_patient_context and has_structured_patient_context:
            yield {"type": "progress", "step": "drugs", "message": "💊 Checking drug interactions…"}
            try:
                drug_safety_alerts = await asyncio.wait_for(
                    asyncio.to_thread(check_drug_interactions, combined_patient_context),
                    timeout=15.0
                )
            except Exception:
                drug_safety_alerts = ""

        # Emit only actual safety alerts to frontend (not treatment recommendations)
        if drug_safety_alerts:
            # Filter: only lines containing actual safety signals
            _ALERT_MARKERS = [
                "DRUG INTERACTION", "CONTRAINDICATION", "QT PROLONGATION",
                "BLEEDING RISK", "DUPLICATE THERAPY", "RENAL DOSE",
                "HEPATIC DOSE", "BEERS CRITERIA",
            ]
            alert_lines = []
            for line in drug_safety_alerts.strip().split("\n"):
                line = line.strip()
                if not line:
                    continue
                if any(marker in line.upper() for marker in _ALERT_MARKERS):
                    alert_lines.append(line)
                # Include indented detail lines (starting with spaces) after an alert
                elif line.startswith("   ") and alert_lines:
                    alert_lines[-1] += "\n" + line
            if alert_lines:
                yield {"type": "drug_alerts", "alerts": alert_lines}

        # ── Step D: Construct prompt ──────────────────────────────────────
        enriched_graph_context = graph_context
        if drug_safety_alerts:
            enriched_graph_context = f"{graph_context}\n\n{drug_safety_alerts}"

        final_prompt = SYNTHESIS_PROMPT.format(
            chat_history=history_text,
            patient_context=patient_context,
            report_context=report_context,
            graph_context=enriched_graph_context,
            vector_context=vector_context,
            vision_context=vision_result,
            query=clean_query
        )

        # ── Step E: Stream LLM synthesis ──────────────────────────────────
        yield {"type": "progress", "step": "synthesis", "message": "🧠 Generating clinical response…"}
        synthesis_temp = temperature if temperature is not None else 0.1
        synthesis_model = model if model else OPENROUTER_MODEL
        print(f"🌡️ Using temperature: {synthesis_temp}")
        print(f"🤖 Using model: {synthesis_model}")

        draft_chunks = []
        if synthesis_model.startswith("vertex/"):
            # Route to MedGemma on Vertex AI with streaming
            print("  🧬 Routing to MedGemma 27B (Vertex AI) for streaming synthesis...")
            for token in call_medgemma_text(
                final_prompt, temperature=synthesis_temp,
                max_tokens=2000, stream=True
            ):
                draft_chunks.append(token)
                yield {"type": "token", "content": token}
        else:
            llm = ChatOpenAI(
                model=synthesis_model,
                openai_api_key=OPENROUTER_API_KEY,
                openai_api_base="https://openrouter.ai/api/v1",
                temperature=synthesis_temp,
                streaming=True
            )
            for chunk in llm.stream(final_prompt):
                token = chunk.content
                if token:
                    draft_chunks.append(token)
                    yield {"type": "token", "content": token}

        draft_response = "".join(draft_chunks)

        # ── Step F: Safety checks ─────────────────────────────────────────
        yield {"type": "progress", "step": "safety", "message": "🛡️ Running safety review…"}

        # F.1: Deterministic Visual-RAG consistency check
        deterministic_override = _check_visual_rag_consistency(vision_result, draft_response)
        if deterministic_override:
            print("  ⚠️ DETERMINISTIC OVERRIDE: Visual-RAG contradicts vision model!")
            draft_response = deterministic_override
            yield {"type": "replace", "content": draft_response}
        else:
            # F.2: Independent LLM Safety Critic
            safety_context = f"""Patient Context: {patient_context}

Uploaded Reports:
{report_context}

Knowledge Graph: {enriched_graph_context}

Vision Analysis & Similar Cases (REVIEW FOR DISCREPANCIES):
{vision_result}
"""
            safety_prompt = SAFETY_CRITIC_PROMPT.format(
                context=safety_context,
                query=clean_query,
                draft=draft_response
            )

            stream_critic_models = [SAFETY_CRITIC_MODEL] + SAFETY_CRITIC_FALLBACKS

            def _make_stream_critic(model_name):
                return ChatOpenAI(
                    model=model_name or SAFETY_CRITIC_MODEL,
                    openai_api_key=OPENROUTER_API_KEY,
                    openai_api_base="https://openrouter.ai/api/v1",
                    temperature=SAFETY_CRITIC_TEMPERATURE
                )

            try:
                critique_text = await asyncio.wait_for(
                    asyncio.to_thread(
                        lambda: _invoke_with_retry(
                            _make_stream_critic, safety_prompt,
                            max_retries=2, models=stream_critic_models
                        )
                    ),
                    timeout=45.0
                )
                verdict_unsafe = "VERDICT: UNSAFE" in critique_text.upper()

                if verdict_unsafe and "CORRECTED_RESPONSE:" in critique_text:
                    corrected = critique_text.split("CORRECTED_RESPONSE:", 1)[1].strip()
                    if len(corrected) > 100:
                        draft_response = corrected
                        yield {"type": "replace", "content": draft_response}
                        print("  ⚠️ Safety Layer OVERRODE the response!")
                    else:
                        print("  ✓ Safety critic flagged UNSAFE but correction too short — keeping draft")
                else:
                    print("  ✓ Safety critic: SAFE")
            except asyncio.TimeoutError:
                print("  ⚠️ Safety critic timed out (45s) — keeping draft")
            except Exception as e:
                print(f"  ⚠️ Safety critic error: {e} — keeping draft")

        # ── Done ──────────────────────────────────────────────────────────
        yield {"type": "done", "final_response": draft_response}

    except Exception as e:
        print(f"❌ Streaming pipeline error: {e}")
        yield {"type": "error", "message": str(e)}

def generate_soap_note(history: list, patient_context: str, vision_context: str = "N/A") -> dict:
    """
    Generates a structured SOAP note from the session context.
    Returns a dict with subjective, objective, assessment, plan sections.
    """
    import json as _json
    from datetime import datetime

    if not history:
        return {"error": "No session history to generate note from."}
        
    history_text = "\n".join([f"{msg['role']}: {msg['content']}" for msg in history])
    
    prompt = SOAP_NOTE_PROMPT.format(
        patient_context=patient_context,
        vision_context=vision_context,
        history=history_text
    )
    
    def _make_soap_llm(model_name):
        return ChatOpenAI(
            model=model_name or OPENROUTER_MODEL,
            openai_api_key=OPENROUTER_API_KEY,
            openai_api_base="https://openrouter.ai/api/v1",
            temperature=0.2
        )

    try:
        raw = _invoke_with_retry(
            _make_soap_llm, prompt, max_retries=3,
            models=["nvidia/nemotron-3-nano-30b-a3b:free"]
        ).strip()
    except Exception as e:
        return {"error": f"LLM call failed after retries: {e}"}
    
    # Try to parse JSON from response
    try:
        # Strip markdown code fences if present
        if raw.startswith("```"):
            raw = raw.split("\n", 1)[1]
            if raw.endswith("```"):
                raw = raw[:-3]
        note = _json.loads(raw)
    except _json.JSONDecodeError:
        # Fallback: wrap raw text
        note = {
            "subjective": {"chief_complaint": raw, "symptoms": []},
            "objective": {"clinical_observations": "See raw note above"},
            "assessment": {"primary_diagnosis": "See raw note", "differential_diagnoses": []},
            "plan": {"medications": [], "follow_up": "See raw note"}
        }
    
    # Add metadata
    note["_metadata"] = {
        "generated_at": datetime.now().isoformat(),
        "note_id": f"SOAP-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
        "message_count": len(history),
    }
    
    return note


# =============================================================================
# Main Execution
# =============================================================================

if __name__ == "__main__":
    test_query = (
        "Assess patient 10002428. Based on their vitals and current diagnosis "
        "of Pneumonia, are there any risks with their current medications?"
    )
    
    asyncio.run(ask_trustmed(test_query))
