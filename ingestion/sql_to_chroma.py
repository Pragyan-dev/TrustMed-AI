import psycopg2
from psycopg2.extras import RealDictCursor
from sentence_transformers import SentenceTransformer
import chromadb
import json
import os
from chromadb.config import Settings
from typing import List, Dict, Any

# ----------------------------
# CONFIG
# ----------------------------

DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "health"
DB_USER = "postgres"
DB_PASSWORD = "Nokia#3310"

CHROMA_DB_DIR = "./chroma_db"
# Create one collection per source table so each becomes an independent agent later.
# These can be overridden with env vars if desired.
CHROMA_COLLECTION_NAMES = {
    "medicines": os.environ.get("CHROMA_COLLECTION_MEDICINES", "medicines"),
    "symptoms": os.environ.get("CHROMA_COLLECTION_SYMPTOMS", "symptoms"),
    "diseases": os.environ.get("CHROMA_COLLECTION_DISEASES", "diseases"),
}

# HuggingFace model (change if you like)
EMBEDDING_MODEL_NAME = "sentence-transformers/all-MiniLM-L6-v2"

# Simple char-based chunking to avoid very long docs
MAX_CHARS_PER_CHUNK = 2000
CHUNK_OVERLAP = 200


# ----------------------------
# HELPER FUNCTIONS
# ----------------------------

def get_connection():
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )
    return conn


def chunk_text(text: str,
               max_chars: int = MAX_CHARS_PER_CHUNK,
               overlap: int = CHUNK_OVERLAP) -> List[str]:
    """
    Split a long string into overlapping chunks.
    """
    if text is None:
        return []

    text = text.strip()
    if not text:
        return []

    chunks = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + max_chars, n)
        chunk = text[start:end]
        chunks.append(chunk)
        if end == n:
            break
        start = max(0, end - overlap)
    return chunks


def fetch_all_rows(conn, table: str, columns: List[str]) -> List[Dict[str, Any]]:
    """
    Fetch all rows for a given table, returning them as dicts.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        col_list = ", ".join(columns)
        query = f"SELECT {col_list} FROM {table};"
        cur.execute(query)
        rows = cur.fetchall()
    return rows


def build_text_for_medicines(row: Dict[str, Any]) -> str:
    return (
        f"Table: medicines\n"
        f"URL: {row.get('source_url', '')}\n"
        f"Title: {row.get('title', '')}\n\n"
        f"Introduction:\n{row.get('introduction', '')}\n\n"
        f"Body:\n{row.get('body', '')}\n\n"
        f"Primary topic: {row.get('primary_topic', '')}\n\n"
        f"Further reading: {row.get('further_reading', '')}\n"
    )


def build_text_for_symptoms(row: Dict[str, Any]) -> str:
    return (
        f"Table: symptoms\n"
        f"Disease name: {row.get('disease_name', '')}\n"
        f"URL: {row.get('source_url', '')}\n\n"
        f"Overview:\n{row.get('overview', '')}\n\n"
        f"Symptoms:\n{row.get('symptoms', '')}\n\n"
        f"Causes:\n{row.get('causes', '')}\n\n"
        f"Risk factors:\n{row.get('risk_factors', '')}\n\n"
        f"Complications:\n{row.get('complications', '')}\n"
    )


def build_text_for_diseases(row: Dict[str, Any]) -> str:
    return (
        f"Table: diseases\n"
        f"Name: {row.get('name', '')}\n"
        f"URL: {row.get('main_url', '')}\n\n"
        f"Description:\n{row.get('description', '')}\n\n"
        f"Symptoms:\n{row.get('symptoms', '')}\n\n"
        f"Causes:\n{row.get('causes', '')}\n\n"
        f"Diagnostics:\n{row.get('diagnosis', '')}\n\n"
        f"Prevention:\n{row.get('prevention', '')}\n\n"
        f"Treatment:\n{row.get('treatment', '')}\n\n"
        f"Living with (advice):\n{row.get('living_with', '')}\n\n"
        f"Questions to ask:\n{row.get('questions_to_ask', '')}\n\n"
        f"Resources:\n{row.get('resources', '')}\n"
    )


def build_docs_and_metadata(
    table_name: str,
    rows: List[Dict[str, Any]],
    text_builder,
) -> tuple[List[str], List[Dict[str, Any]], List[str]]:
    """
    For each row, build one or more text chunks + metadata + unique ids.
    """
    documents = []
    metadatas = []
    ids = []

    for row_index, row in enumerate(rows):
        base_text = text_builder(row)
        chunks = chunk_text(base_text)

        if not chunks:
            # Still keep an empty record if you want; otherwise skip
            continue

        for chunk_idx, chunk in enumerate(chunks):
            doc_id = f"{table_name}_{row_index}_chunk_{chunk_idx}"

            documents.append(chunk)
            metadata = {
                "table": table_name,
                "collection": table_name,
                "row_index": row_index,
                "chunk_index": chunk_idx,
                # a few useful fields for filtering
                # include a canonical url field if present in the row
                "url": (row.get("source_url") or row.get("main_url") or row.get("url") or None),
                # store the full row as a JSON string so metadata stays primitive-typed
                "row": json.dumps(dict(row) if isinstance(row, dict) else row, ensure_ascii=False, default=str),
            }

            if table_name == "symptoms":
                metadata["disease_name"] = row.get("disease_name")
            if table_name == "diseases":
                metadata["disease_name"] = row.get("name")
            if table_name == "medicines":
                metadata["title"] = row.get("title") or row.get("meta_title")

            metadatas.append(metadata)
            ids.append(doc_id)

    return documents, metadatas, ids


# ----------------------------
# MAIN PIPELINE
# ----------------------------

def main():
    # 1. connect to DB
    conn = get_connection()
    print("Connected to PostgreSQL")

    # 2. Load data from each table
    #    Adjust column names if they differ in your DB
    medicines_cols = [
        "source_url",
        "title",           # or "meta_title" if that's your column name
        "introduction",
        "body",
        "primary_topic",
        "further_reading",
    ]

    symptoms_cols = [
        "disease_name",
        "source_url",
        "overview",
        "symptoms",
        "causes",
        "risk_factors",
        "complications",
    ]

    diseases_cols = [
        "name",
        "main_url",
        "description",
        "symptoms",
        "causes",
        "diagnosis",
        "prevention",
        "treatment",
        "living_with",
        "questions_to_ask",
        "resources",
    ]

    medicines_rows = fetch_all_rows(conn, "medicines", medicines_cols)
    symptoms_rows = fetch_all_rows(conn, "symptoms", symptoms_cols)
    diseases_rows = fetch_all_rows(conn, "diseases", diseases_cols)

    print(f"Fetched {len(medicines_rows)} medicines, "
          f"{len(symptoms_rows)} symptoms, "
          f"{len(diseases_rows)} diseases")

    # 3. Build documents + metadata
    med_docs, med_meta, med_ids = build_docs_and_metadata(
        "medicines", medicines_rows, build_text_for_medicines
    )
    sym_docs, sym_meta, sym_ids = build_docs_and_metadata(
        "symptoms", symptoms_rows, build_text_for_symptoms
    )
    dis_docs, dis_meta, dis_ids = build_docs_and_metadata(
        "diseases", diseases_rows, build_text_for_diseases
    )

    all_docs = med_docs + sym_docs + dis_docs
    all_meta = med_meta + sym_meta + dis_meta
    all_ids = med_ids + sym_ids + dis_ids

    print(f"Total chunks to embed: {len(all_docs)}")

    if not all_docs:
        print("No documents to embed; exiting.")
        return

    # 4. Init embedding model
    model = SentenceTransformer(EMBEDDING_MODEL_NAME)
    print(f"Loaded embedding model: {EMBEDDING_MODEL_NAME}")

    # 5. Init Chroma and create one collection per table
    client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
    collections = {}
    # Attach collection-level metadata so the orchestrator can reason about which
    # collections to activate for a query.
    meta_by_key = {
        "medicines": {
            "table": "medicines",
            "fields": {
                "source_url": "Original URL of the medical article or page.",
                "title": "Title of the medicine or article, typically the name of the drug or treatment.",
                "introduction": "Introductory summary or abstract of the medicine content.",
                "body": "Full text or main body describing dosage, side effects, usage, etc.",
                "primary_topic": "Main subject category, e.g., Antibiotic, Analgesic, Vaccine, etc.",
                "further_reading": "References or related articles linked to the medicine.",
            },
        },
        "symptoms": {
            "table": "symptoms",
            "fields": {
                "disease_name": "Name of the disease or condition associated with the symptoms.",
                "source_url": "Source link to the medical content.",
                "overview": "Short description or summary of the condition.",
                "symptoms": "List or textual description of symptoms associated with the disease.",
                "causes": "Known or suspected causes of the condition.",
                "risk_factors": "Factors that increase the likelihood of developing the condition.",
                "complications": "Possible health complications resulting from the disease.",
            },
        },
        "diseases": {
            "table": "diseases",
            "fields": {
                "name": "Name of the disease or condition.",
                "main_url": "Primary source URL of the disease page.",
                "description": "General overview or background about the disease.",
                "symptoms": "List or description of common symptoms.",
                "causes": "Underlying causes or contributing factors.",
                "diagnosis": "Information on how the disease is diagnosed (tests, procedures, etc.).",
                "prevention": "Preventive measures or lifestyle tips.",
                "treatment": "Treatment methods, therapies, or medications used.",
                "living_with": "Advice for managing or living with the condition.",
                "questions_to_ask": "Common patient questions to ask healthcare providers.",
                "resources": "External references or links for further reading.",
            },
        },
    }

    for key, name in CHROMA_COLLECTION_NAMES.items():
        base_meta = {"hnsw:space": "cosine"}
        table_meta = meta_by_key.get(key, {})
        # Chroma collection metadata only supports primitive scalars. Flatten dicts.
        table_meta_flat = dict(table_meta)
        if isinstance(table_meta_flat.get("fields"), dict):
            try:
                table_meta_flat["fields_json"] = json.dumps(table_meta_flat["fields"], ensure_ascii=False)
            except Exception:
                table_meta_flat["fields_json"] = str(table_meta_flat["fields"])  # fallback
            table_meta_flat.pop("fields", None)
        merged_meta = {**base_meta, **table_meta_flat}
        col = client.get_or_create_collection(name=name, metadata=merged_meta)
        try:
            # Ensure metadata is refreshed if collection already existed
            col.modify(metadata=merged_meta)
        except Exception:
            pass
        collections[key] = col
        print(f"Using Chroma collection for {key}: {name}")

    # 6. Compute embeddings and push to the corresponding collection per table
    batch_size = 64

    def _push_to_collection(col_obj, docs_list, ids_list, meta_list):
        if not docs_list:
            return
        for start in range(0, len(docs_list), batch_size):
            end = start + batch_size
            batch_docs = docs_list[start:end]
            batch_ids = ids_list[start:end]
            batch_meta = meta_list[start:end]

            embeddings = model.encode(batch_docs, show_progress_bar=False)
            col_obj.add(
                ids=batch_ids,
                embeddings=embeddings.tolist(),  # Chroma expects list of lists
                metadatas=batch_meta,
                documents=batch_docs,
            )
            print(f"Inserted {len(batch_docs)} docs into collection {col_obj.name} ({end}/{len(docs_list)})")

    _push_to_collection(collections["medicines"], med_docs, med_ids, med_meta)
    _push_to_collection(collections["symptoms"], sym_docs, sym_ids, sym_meta)
    _push_to_collection(collections["diseases"], dis_docs, dis_ids, dis_meta)

    # 7. Report per-collection counts to verify three separate collections exist
    try:
        for key, name in CHROMA_COLLECTION_NAMES.items():
            col = collections.get(key)
            if col is not None:
                print(f"Collection '{col.name}' document count: {col.count()}")
    except Exception as e:
        print(f"Warning: could not fetch collection counts: {e}")

    conn.close()
    print("Done! Your PostgreSQL DB is now mirrored in a Chroma vector store.")


if __name__ == "__main__":
    main()
