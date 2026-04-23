# Synapse AI (TrustMed AI)

Synapse AI is a multimodal clinical decision support platform built as a capstone project. It brings together patient context, medical knowledge graph search, vector retrieval, and medical image analysis in a single system with dedicated experiences for clinicians and patients.

The current implementation is built on a `Next.js + React` frontend, a `FastAPI` backend, and a neuro-symbolic orchestration layer in `src/trustmed_brain.py`.

## Highlights

- Clinician dashboard with streaming chat, session history, patient selection, image upload, graph context, drug safety alerts, and SOAP note generation
- Patient portal with vitals, diagnoses, medications, care-plan summaries, and attachment viewing
- Neuro-symbolic orchestration that combines patient data, graph retrieval, vector retrieval, and multimodal reasoning
- Medical image pipeline with upload handling, compound figure detection, and per-panel analysis
- Knowledge graph integration through Neo4j and semantic retrieval through ChromaDB
- Evaluation and ingestion tooling for expanding the demo and testing the system

## Applications

### Clinician dashboard

The clinician workflow is available at `/clinician` and is designed for richer decision support. It includes:

- patient-aware chat
- streaming responses
- text and vision model selection
- knowledge graph exploration
- drug safety summaries
- image upload and panel analysis
- SOAP note generation

### Patient portal

The patient workflow is available at `/patient` and focuses on a simpler view of the same clinical context. It includes:

- patient summary views
- vitals trend charts
- medication and diagnosis summaries
- care-plan generation
- attachment viewing and upload

## Architecture Overview

```text
Next.js frontend
    -> /api rewrites
    -> FastAPI backend
        -> TrustMed Brain orchestrator
            -> patient context from local SQLite demo data
            -> graph context from Neo4j
            -> vector context from ChromaDB
            -> multimodal image analysis
        -> JSON and SSE responses back to the UI
```

The system centers on three major context channels:

- Patient context from local demo records and processed attachments
- Graph context from Neo4j-backed medical relationships
- Vector context from indexed medical content stored in ChromaDB

## Tech Stack

- Frontend: `Next.js 15`, `React 19`, App Router
- Backend: `FastAPI`, `uvicorn`, SSE streaming
- Retrieval: `ChromaDB`, `Sentence Transformers`, reranking
- Graph: `Neo4j`, `langchain-neo4j`
- Multimodal/LLM: `OpenRouter`, `Vertex AI MedGemma`, custom vision orchestration
- Data: local SQLite demo database, SQL seed data, uploaded patient attachments

## Project Structure

```text
synapse/
├── README.md
├── api/                  # FastAPI routes and backend API surface
├── frontend/             # Next.js app and React UI
├── src/                  # orchestration, retrieval, graph, vision, and patient context logic
├── ingestion/            # ingestion pipelines for graph and retrieval data
├── scripts/              # local bootstrap and baseline population scripts
├── tests/                # evaluation and verification scripts
├── results/              # saved evaluation outputs
├── setup_health_db.sql   # seed medical content used by baseline pipelines
├── run_dev.sh            # start frontend + backend together
└── app.py                # legacy Streamlit prototype
```

## Getting Started

### Prerequisites

- Python 3
- Node.js and npm
- Neo4j for graph-backed features
- OpenRouter and optionally Vertex AI credentials for model-backed features

### Install Dependencies

Backend:

```bash
pip install -r requirements.txt
```

Frontend:

```bash
cd frontend
npm install
cd ..
```

### Environment Variables

Create a `.env` file in the project root and provide the values you need for your setup.

| Variable | Purpose |
| --- | --- |
| `OPENROUTER_API_KEY` | Required for default text generation flows |
| `OPENROUTER_MODEL` | Optional override for the default text model |
| `SAFETY_CRITIC_MODEL` | Optional override for the review model |
| `NEO4J_URI` | Required for graph features |
| `NEO4J_USERNAME` | Neo4j username |
| `NEO4J_PASSWORD` | Neo4j password |
| `VERTEX_PROJECT_ID` | Required for Vertex AI MedGemma usage |
| `VERTEX_ENDPOINT_ID` | Required for Vertex AI MedGemma usage |
| `VERTEX_REGION` | Vertex region |
| `VERTEX_SERVICE_ACCOUNT_JSON` | Optional service account path |
| `VERTEX_DEDICATED_DOMAIN` | Vertex endpoint domain |
| `UMLS_API_KEY` | Optional UMLS enrichment support |

### Bootstrap Local Data

```bash
python3 scripts/init_sample_db.py
python3 scripts/populate_baseline_chroma.py
python3 scripts/populate_baseline_graph.py
```

These scripts:

- create the local demo patient database
- build the baseline Chroma vector store
- populate the baseline Neo4j graph

### Run the Application

Preferred:

```bash
./run_dev.sh
```

This starts:

- frontend on `http://localhost:5173`
- backend on `http://localhost:8000`
- API docs on `http://localhost:8000/docs`

Manual startup:

Backend:

```bash
cd api
python3 -m uvicorn main:app --reload --port 8000 --reload-dir ../api --reload-dir ../src
```

Frontend:

```bash
cd frontend
npm run dev
```

## Usage

- Open `http://localhost:5173`
- Choose the clinician or patient workflow from the landing page
- Use a sample patient record to explore patient-aware chat and summaries
- Upload medical imaging in the clinician workflow to trigger multimodal analysis

The frontend proxies backend requests through `/api/...` using rewrites defined in `frontend/next.config.mjs`.

## Testing and Evaluation

The repository includes several useful validation scripts:

- `python3 tests/test_api_evaluation.py`
- `python3 tests/evaluate_system.py`
- `python3 tests/evaluate_system_comprehensive.py`
- `python3 tests/performance_test_extensive.py`
- `python3 tests/test_patient_attachments.py`

## Included Pipelines

Beyond the web app, the repository also includes:

- baseline graph and vector population scripts
- broader ingestion pipelines for SQL, MIMIC, and medical imaging datasets
- patient report parsing and attachment summarization utilities
- a legacy Streamlit prototype preserved in `app.py`
