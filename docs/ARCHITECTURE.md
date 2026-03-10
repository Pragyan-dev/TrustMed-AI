# TrustMed AI - System Architecture

## High-Level Architecture

```mermaid
flowchart TB
    subgraph UI[User Interface]
        ST[Streamlit Dashboard]
    end
    
    subgraph BRAIN[TrustMed Brain - Orchestrator]
        direction TB
        ORCH[trustmed_brain.py]
        
        subgraph SOURCES[Knowledge Sources]
            direction LR
            PC[Patient Context]
            GS[Graph Search]
            VS[Vector Search]
        end
        
        FUSION[Context Fusion]
    end
    
    subgraph DATA[Data Layer]
        direction LR
        SQLITE[(SQLite)]
        NEO4J[(Neo4j)]
        CHROMA[(ChromaDB)]
    end
    
    subgraph LLM[LLM Layer]
        OPENROUTER[OpenRouter API]
    end
    
    ST --> ORCH
    ORCH --> PC
    ORCH --> GS
    ORCH --> VS
    PC --> SQLITE
    GS --> NEO4J
    VS --> CHROMA
    PC --> FUSION
    GS --> FUSION
    VS --> FUSION
    FUSION --> OPENROUTER
    OPENROUTER --> ST
```

---

## Data Flow Diagram

```mermaid
sequenceDiagram
    participant U as User
    participant UI as Streamlit
    participant B as Brain
    participant SQL as SQLite
    participant N4J as Neo4j
    participant C as ChromaDB
    participant LLM as OpenRouter

    U->>UI: Query with Patient ID
    UI->>B: ask_trustmed query
    
    par Parallel Fetch
        B->>SQL: Patient Data
        SQL-->>B: Vitals, Meds
    and
        B->>N4J: Cypher Query
        N4J-->>B: Disease Facts
    and
        B->>C: Vector Search
        C-->>B: Documents
    end
    
    B->>B: Fuse Contexts
    B->>LLM: Generate Response
    LLM-->>B: Clinical Assessment
    B-->>UI: Response
    UI-->>U: Display
```

---

## Data Ingestion Pipeline

```mermaid
flowchart LR
    subgraph INPUT[Raw Data]
        CSV1[MIMIC CSVs]
        CSV2[Kaggle CSVs]
        PG[(PostgreSQL)]
    end
    
    subgraph INGESTION[Ingestion Scripts]
        I1[ingest_mimic.py]
        I2[ingest_kaggle.py]
        I3[sql_to_chroma.py]
        UMLS[UMLS Validation]
    end
    
    subgraph OUTPUT[Data Stores]
        SQLITE[(SQLite - 5873 rows)]
        NEO4J[(Neo4j Graph)]
        CHROMA[(ChromaDB - 9463 docs)]
    end
    
    CSV1 --> I1 --> SQLITE
    CSV2 --> I2 --> UMLS --> NEO4J
    PG --> I3 --> CHROMA
```

---

## Component Summary

| Component | Technology | Files |
|-----------|------------|-------|
| UI | Streamlit | `app.py` |
| Orchestrator | Python/asyncio | `src/trustmed_brain.py` |
| Patient Data | SQLite | `src/patient_context_tool.py` |
| Graph Search | Neo4j/Cypher | `src/graph_tool.py` |
| Vector Search | ChromaDB | `src/hybrid_search.py` |
| LLM | OpenRouter | nvidia/nemotron |

---

## Query Processing Steps

1. **User Input** → Streamlit captures query
2. **Patient Detection** → Regex finds patient ID (10XXXXXX)
3. **Parallel Fetch**:
   - SQLite: vitals, diagnoses, medications
   - Neo4j: disease facts, symptoms, precautions
   - ChromaDB: relevant medical documents
4. **Context Fusion** → Combine all three contexts
5. **LLM Synthesis** → Generate clinical assessment
6. **Response** → Display in chat interface
