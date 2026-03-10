# TrustMed-AI: Knowledge Graph Integration

A medical AI chatbot with hybrid retrieval using both vector search (ChromaDB) and knowledge graph queries (Neo4j).

## 🆕 Changes - January 24, 2026

### New Features Added

#### 1. BioCypher Schema Configuration (`schema_config.yaml`)
- Defined graph schema mapping PostgreSQL tables to knowledge graph nodes
- **Nodes**: `Drug`, `Disease`, `Symptom`
- **Relationships**: `TREATS` (Drug→Disease), `HAS_SYMPTOM` (Disease→Symptom)
- Includes property definitions with types and descriptions

#### 2. Neo4j Knowledge Graph Pipeline (`sql_to_graph.py`)
- Extracts data from PostgreSQL and loads into Neo4j
- Uses **spaCy biomedical NER** (`en_ner_bc5cdr_md`) for entity extraction
- Creates Disease nodes and Symptom nodes with relationships
- Uses `MERGE` to handle duplicates gracefully

#### 3. LangChain Graph Tool (`graph_tool.py`)
- `GraphRetriever` tool for natural language → Cypher queries
- Uses **OpenRouter API** with `nvidia/nemotron-3-nano-30b-a3b:free` model
- Integrates with `GraphCypherQAChain` for automatic query generation
- Ready for LangChain agent integration

#### 4. Hybrid Search (`hybrid_search.py`)
- Combines vector search (ChromaDB) and graph search (Neo4j)
- **Parallel execution** using `asyncio` for optimal performance
- Graceful error handling - if one fails, the other still returns
- Returns combined context for RAG pipeline

#### 5. Database Setup (`setup_health_db.sql`)
- SQL script to create and populate the `health` database
- Sample data: 8 medicines, 8 diseases, 6 symptom records
- Includes indexes for performance

#### 6. Environment Configuration (`.env`)
- Centralized API keys and database credentials
- Neo4j, OpenRouter, PostgreSQL, ChromaDB configs

---

## 📊 Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        User Query                                │
└─────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────┐
│                     hybrid_search()                              │
│                   (Parallel Execution)                           │
└─────────────────────────────────────────────────────────────────┘
                    │                    │
          ┌─────────┘                    └─────────┐
          ▼                                        ▼
┌──────────────────────┐              ┌──────────────────────┐
│   Vector Search      │              │    Graph Search      │
│   (ChromaDB)         │              │    (Neo4j)           │
│                      │              │                      │
│ • Semantic similarity│              │ • Structured queries │
│ • Top-k chunks       │              │ • Relationship paths │
│ • Fast retrieval     │              │ • Entity connections │
└──────────────────────┘              └──────────────────────┘
          │                                        │
          └────────────────┬───────────────────────┘
                           ▼
┌─────────────────────────────────────────────────────────────────┐
│                    Combined Context                              │
│  --- VECTOR CONTEXT ---                                         │
│  [Relevant document chunks]                                     │
│                                                                 │
│  --- GRAPH CONTEXT ---                                          │
│  [Structured relationship data]                                 │
└─────────────────────────────────────────────────────────────────┘
```

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip3 install neo4j langchain langchain-community langchain-openai chromadb sentence-transformers scispacy python-dotenv
pip3 install https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_ner_bc5cdr_md-0.5.4.tar.gz
```

### 2. Start PostgreSQL
```bash
brew services start postgresql@14
```

### 3. Setup Database
```bash
createdb health
psql -d health -f setup_health_db.sql
```

### 4. Populate Neo4j Knowledge Graph
```bash
python3 sql_to_graph.py
```

### 5. Use Hybrid Search
```python
from hybrid_search import hybrid_search

result = hybrid_search("What symptoms are associated with Type 2 Diabetes?")
print(result)
```

---

## 📁 New Files Created Today

| File | Purpose |
|------|---------|
| `schema_config.yaml` | BioCypher schema for knowledge graph |
| `sql_to_graph.py` | PostgreSQL → Neo4j pipeline with NER |
| `graph_tool.py` | LangChain tool for graph queries |
| `hybrid_search.py` | Parallel vector + graph search |
| `setup_health_db.sql` | Database schema and sample data |
| `.env` | Environment variables |

---

## 🔧 Configuration

Environment variables in `.env`:
```
NEO4J_URI=neo4j+s://dbde172c.databases.neo4j.io
NEO4J_USERNAME=neo4j
NEO4J_PASSWORD=<your-password>
OPENROUTER_API_KEY=<your-api-key>
OPENROUTER_MODEL=nvidia/nemotron-3-nano-30b-a3b:free
```

---

## 📈 Neo4j Database Stats

After running `sql_to_graph.py`:
- **8 Disease nodes** (Diabetes, Hypertension, Asthma, etc.)
- **61 Symptom nodes** (extracted via biomedical NER)
- **76 HAS_SYMPTOM relationships**

---

## 🧪 Example Queries

```python
# Hybrid search
hybrid_search("What causes asthma?")
hybrid_search("What drugs treat high blood pressure?")

# Direct graph query
from graph_tool import query_graph
query_graph("List all diseases in the database")
query_graph("What conditions cause fatigue?")
```

---

## 📝 Next Steps

- [ ] Populate ChromaDB by running `sql_to_chroma.py`
- [ ] Integrate hybrid search into main RAG pipeline (`anti_test.py`)
- [ ] Add Drug nodes and TREATS relationships
- [ ] Implement result deduplication between vector and graph results
- [ ] Add caching for frequent queries

---

## 👥 Contributors

Built as part of the TrustMed-AI capstone project.
