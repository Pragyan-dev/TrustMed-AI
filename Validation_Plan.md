# TrustMed AI Validation Master Plan

## 1. Purpose

This document defines a reportable, reproducible, and execution-ready validation plan for the TrustMed AI project. It turns the current project structure into a linear validation program where each execution step produces a specific validation outcome and a named evidence artifact.

The plan is designed for the active product surface in this repository:

- FastAPI backend in `api/main.py`
- Next.js frontend in `frontend/`
- Core orchestration and retrieval logic in `src/`
- Ingestion and dataset preparation scripts in `ingestion/`
- Existing validation scripts in `tests/`

The legacy Streamlit app in `app.py` is included as a separate compatibility surface, not as the primary product path.

## 2. Scope

### In Scope

- Environment readiness and dependency validation
- Backend static validation and API contract validation
- Clinician workflow validation
- Patient workflow validation
- Core AI orchestration validation
- Patient context, vector retrieval, graph retrieval, and vision pipeline validation
- Data store and ingestion validation
- Performance, resilience, and persistence validation
- Regression validation and release signoff
- Validation reporting templates and evidence structure

### Out of Scope Unless Explicitly Requested

- Production security hardening
- Compliance certification
- Penetration testing by external tools
- Cloud deployment validation
- Network/firewall administration outside the local runtime

## 3. Validation Principles

1. **Linear traceability**  
   Every phase maps to a named artifact and a pass/fail outcome.

2. **Reproducibility**  
   Every run must record commit SHA, environment state, test data, timestamps, and raw outputs.

3. **Separation of concerns**  
   Static, integration, AI-quality, data, performance, and manual UX validation are reported separately.

4. **Deterministic evidence collection**  
   All commands run from the repository root unless stated otherwise.

5. **Status model**  
   Each test result must be marked as one of:
   - `PASS`
   - `FAIL`
   - `BLOCKED`
   - `NOT RUN`

## 4. Repository Baseline

Primary files and locations used by this plan:

- Backend API: `api/main.py`
- Orchestrator: `src/trustmed_brain.py`
- Patient context: `src/patient_context_tool.py`
- Vision pipeline: `src/vision_agent.py`
- Graph visualization: `src/graph_visualizer.py`
- Clinician UI: `frontend/src/views/ClinicianDashboard.jsx`
- Patient UI: `frontend/src/views/PatientPortal.jsx`
- Existing API evaluation: `tests/test_api_evaluation.py`
- Existing comprehensive evaluation: `tests/evaluate_system_comprehensive.py`
- Existing performance evaluation: `tests/performance_test_extensive.py`
- Existing context-switch evaluation: `tests/test_context_switch.py`

## 5. Standard Execution Conventions

### 5.1 Working Directory

All commands in this document assume the shell starts in:

```powershell
Set-Location "C:\ASU\Sem 4\code\TrustMed-AI"
```

### 5.2 Standard Run Identifier

Create one run identifier per validation execution:

```powershell
$RunId = Get-Date -Format "yyyyMMdd_HHmmss"
```

### 5.3 Standard Evidence Folder

```powershell
New-Item -ItemType Directory -Force -Path ".\validation_runs\$RunId" | Out-Null
```

### 5.4 Standard Metadata Capture

```powershell
git rev-parse HEAD | Out-File ".\validation_runs\$RunId\commit.txt"
python --version | Out-File ".\validation_runs\$RunId\python_version.txt"
node --version | Out-File ".\validation_runs\$RunId\node_version.txt"
npm --version | Out-File ".\validation_runs\$RunId\npm_version.txt"
```

## 6. Execution Flow and Artifact Map

| Step | Phase | Test IDs | Main Objective | Output Artifact | Gate to Next Step |
|---|---|---|---|---|---|
| 0 | Preflight | `ENV-*` | Confirm environment, config, data, and services exist | `00_preflight.md` | No critical `FAIL` or unresolved `BLOCKED` |
| 1 | Static validation | `STA-*` | Confirm codebase builds/imports/lints cleanly | `01_static.md` | Backend and frontend are buildable |
| 2 | Backend contract | `API-*` | Validate API endpoints and payload contracts | `02_api.md` | Core endpoints pass |
| 3 | Clinician workflow | `CLI-*` | Validate clinician UI and end-to-end flow | `03_clinician.md` | Clinician journey passes |
| 4 | Patient workflow | `PAT-*` | Validate patient UI, safety scope, and summaries | `04_patient.md` | Patient journey passes |
| 5 | Core AI quality | `AI-*` | Validate RAG quality, context handling, and consistency | `05_ai_quality.md` | AI core quality is acceptable |
| 6 | Vision pipeline | `VIS-*` | Validate image upload, compound detection, and cache behavior | `06_vision.md` | Vision path passes |
| 7 | Data and ingestion | `DAT-*` | Validate SQLite, ChromaDB, Neo4j, and ingestion assumptions | `07_data.md` | Data layer is consistent |
| 8 | Performance | `PERF-*` | Validate latency, concurrency, stability, and persistence | `08_performance.md` | Performance is acceptable |
| 9 | Legacy surface | `LEG-*` | Smoke-check Streamlit legacy path if retained | `09_legacy.md` | Legacy path status documented |
| 10 | Signoff | `REL-*` | Summarize blockers, coverage, and release confidence | `10_signoff.md` | Final validation decision |

## 7. Required Test Data and Fixtures

The following fixtures should be standardized before a formal full run:

| Fixture ID | Path | Purpose | Required For |
|---|---|---|---|
| `FX-PAT-01` | Built-in patient IDs: `10002428`, `10025463`, `10027602`, `10009049` | Stable patient-context regression checks | `API-*`, `CLI-*`, `PAT-*`, `AI-*` |
| `FX-VIS-01` | `tests/fixtures/vision/single_panel_xray.png` | Single-image vision validation | `VIS-*` |
| `FX-VIS-02` | `tests/fixtures/vision/compound_figure.png` | Multi-panel compound detection validation | `VIS-*` |
| `FX-CHAT-01` | Standard query list in report appendix | Stable chat regression prompts | `API-*`, `AI-*`, `PERF-*` |
| `FX-TERM-01` | Medical terms: `tachycardia`, `hypertension`, `pneumonia` | Explain-term cache validation | `PAT-*`, `API-*` |

If `FX-VIS-01` and `FX-VIS-02` do not yet exist, the run must be marked `BLOCKED` for the affected vision tests instead of failing the full program.

## 8. Environment Startup Commands

### Backend

```powershell
Set-Location "C:\ASU\Sem 4\code\TrustMed-AI\api"
python -m uvicorn main:app --reload --port 8000
```

### Frontend

```powershell
Set-Location "C:\ASU\Sem 4\code\TrustMed-AI\frontend"
npm run dev
```

### Manual URLs

- Frontend root: `http://localhost:5173`
- Clinician UI: `http://localhost:5173/clinician`
- Patient UI: `http://localhost:5173/patient`
- Backend root: `http://127.0.0.1:8000/`
- Backend docs: `http://127.0.0.1:8000/docs`

## 9. Detailed Test Matrix

---

## Phase 0 - Preflight Validation

| Test ID | Objective | Exact Command | Expected Output | Evidence | Outcome Rule |
|---|---|---|---|---|---|
| `ENV-001` | Verify Python is present | `python --version` | Python 3.x prints successfully | `00_preflight.md` | `PASS` if exit code is 0 |
| `ENV-002` | Verify Node is present | `node --version` | Node version prints successfully | `00_preflight.md` | `PASS` if exit code is 0 |
| `ENV-003` | Verify npm is present | `npm --version` | npm version prints successfully | `00_preflight.md` | `PASS` if exit code is 0 |
| `ENV-004` | Verify backend Python dependencies | `python -c "import fastapi, uvicorn, chromadb, neo4j, sentence_transformers, streamlit; print('python_deps_ok')"` | `python_deps_ok` | `00_preflight.md` | `PASS` if string prints with exit code 0 |
| `ENV-005` | Verify frontend package manifest exists | `Test-Path ".\frontend\package.json"` | `True` | `00_preflight.md` | `PASS` if `True` |
| `ENV-006` | Verify `.env` exists | `Test-Path ".\.env"` | `True` | `00_preflight.md` | `BLOCKED` if `False` for dynamic AI tests |
| `ENV-007` | Verify required env keys are present | `python -c "from dotenv import dotenv_values; c=dotenv_values('.env'); req=['OPENROUTER_API_KEY','NEO4J_URI','NEO4J_USERNAME','NEO4J_PASSWORD']; print({k:bool(c.get(k)) for k in req})"` | All required keys map to `True` | `00_preflight.md` | `PASS` if all required keys are truthy |
| `ENV-008` | Verify SQLite demo DB exists | `Test-Path ".\data\mimic_demo.db"` | `True` | `00_preflight.md` | `BLOCKED` if `False` for patient tests |
| `ENV-009` | Verify Chroma store exists | `Test-Path ".\data\chroma_db"` | `True` | `00_preflight.md` | `BLOCKED` if `False` for retrieval tests |
| `ENV-010` | Verify Neo4j connectivity | `python -c "from dotenv import dotenv_values; from neo4j import GraphDatabase; c=dotenv_values('.env'); drv=GraphDatabase.driver(c['NEO4J_URI'], auth=(c['NEO4J_USERNAME'], c['NEO4J_PASSWORD'])); drv.verify_connectivity(); print('neo4j_ok')"` | `neo4j_ok` | `00_preflight.md` | `PASS` if connectivity succeeds |
| `ENV-011` | Verify runtime directories can be created | `python -c "import api.main; print('runtime_dirs_ok')"` | `runtime_dirs_ok` and folders created if missing | `00_preflight.md` | `PASS` if import succeeds |
| `ENV-012` | Verify git SHA can be captured | `git rev-parse HEAD` | Full commit SHA | `commit.txt` | `PASS` if SHA prints |

### Recommended Split Across Two Systems

If you want to run the first ten preflight tests on two different systems, use this split:

#### System A - Tooling and Static Prerequisites

Run these on the machine intended to validate local toolchain readiness:

- `ENV-001`
- `ENV-002`
- `ENV-003`
- `ENV-004`
- `ENV-005`

These checks confirm that the system has the required local executables, Python packages, and frontend manifest needed for static validation.

#### System B - Runtime Configuration and Data Dependencies

Run these on the machine intended to validate runtime-backed dependencies:

- `ENV-006`
- `ENV-007`
- `ENV-008`
- `ENV-009`
- `ENV-010`

These checks confirm that the system has the `.env` file, required credentials, local databases, vector store, and Neo4j connectivity needed for integration and runtime validation.

#### Consolidation Rule

The two systems can execute these checks independently, but the preflight phase is only considered complete when results from both systems are merged into the same `00_preflight.md` report.

#### Recommended Ownership

| System | Assigned Tests | Purpose | Can It Unblock Later Phases Alone? |
|---|---|---|---|
| System A | `ENV-001` to `ENV-005` | Tooling and static readiness | No |
| System B | `ENV-006` to `ENV-010` | Runtime config and data readiness | No |

Both systems must report successful results before the full preflight gate is marked complete.

---

## Phase 1 - Static Validation

| Test ID | Objective | Exact Command | Expected Output | Evidence | Outcome Rule |
|---|---|---|---|---|---|
| `STA-001` | Backend import smoke | `python -c "import api.main; print('backend_import_ok')"` | `backend_import_ok` | `01_static.md` | `PASS` if import succeeds |
| `STA-002` | Compile backend and scripts | `python -m compileall api src ingestion tests` | No `*** Failed` lines | `01_static.md` | `PASS` if exit code is
 0 |
| `STA-003` | Count FastAPI routes | `python -c "from api.main import app; print(len(app.routes))"` | Integer greater than 0 | `01_static.md` | `PASS` if route count is non-zero |
| `STA-004` | Verify frontend lint | `Set-Location ".\frontend"; npm run lint` | ESLint exits cleanly | `01_static.md` | `PASS` if exit code is 0 |
| `STA-005` | Verify frontend production build | `Set-Location ".\frontend"; npm run build` | Next build completes successfully | `01_static.md` | `PASS` if exit code is 0 |
| `STA-006` | Verify rewrite configuration | `Get-Content ".\frontend\next.config.mjs"` | `/api/:path*` rewrites to `http://localhost:8000/:path*` | `01_static.md` | `PASS` if rewrite matches backend |
| `STA-007` | Verify backend request models exist | `Select-String -Path ".\api\main.py" -Pattern "class ChatRequest|class ChatResponse|class SOAPRequest"` | All classes found | `01_static.md` | `PASS` if all are present |
| `STA-008` | Verify path consistency for data stores | `Select-String -Path ".\src\*.py",".\tests\*.py",".\docs\*.md" -Pattern "chroma_db|mimic_demo.db"` | Paths are documented and explainable | `01_static.md` | `PASS` if no unexplained path mismatch remains |

---

## Phase 2 - Backend API Contract Validation

Before running the commands below:

```powershell
$Base = "http://127.0.0.1:8000"
$ClinicianSession = (Invoke-RestMethod -Method Post "$Base/sessions/new?source=clinician").id
$PatientSession = (Invoke-RestMethod -Method Post "$Base/sessions/new?source=patient").id
```

| Test ID | Objective | Exact Command | Expected Output | Evidence | Outcome Rule |
|---|---|---|---|---|---|
| `API-001` | Health endpoint | `Invoke-RestMethod "$Base/" | ConvertTo-Json -Depth 5` | JSON contains `message` and `version` = `2.0.0` | `02_api.md` | `PASS` if both keys are returned |
| `API-002` | Session create - clinician | `Invoke-RestMethod -Method Post "$Base/sessions/new?source=clinician" | ConvertTo-Json -Depth 5` | JSON contains non-empty `id` | `02_api.md` | `PASS` if `id` is created |
| `API-003` | Session list | `Invoke-RestMethod "$Base/sessions?source=clinician" | ConvertTo-Json -Depth 5` | JSON contains `sessions` array | `02_api.md` | `PASS` if current session appears |
| `API-004` | Session fetch | `Invoke-RestMethod "$Base/sessions/$ClinicianSession" | ConvertTo-Json -Depth 8` | JSON contains `id`, `title`, `messages` | `02_api.md` | `PASS` if session loads |
| `API-005` | Patient lookup | `Invoke-RestMethod "$Base/patient/10002428" | ConvertTo-Json -Depth 8` | JSON contains `patient_id`, `vitals`, `diagnoses`, `medications` | `02_api.md` | `PASS` if all keys exist |
| `API-006` | Patient summary | `Invoke-RestMethod -Method Post "$Base/patient/10002428/summary" | ConvertTo-Json -Depth 8` | JSON contains `summary`, `vitals_explanation`, `medications_explanation`, `next_steps` | `02_api.md` | `PASS` if structure is complete |
| `API-007` | Explain term | `Invoke-RestMethod "$Base/explain-term?term=tachycardia" | ConvertTo-Json -Depth 5` | JSON contains `term`, `explanation`, `cached` | `02_api.md` | `PASS` if explanation is non-empty |
| `API-008` | Explain term cache hit | `Invoke-RestMethod "$Base/explain-term?term=tachycardia" | ConvertTo-Json -Depth 5` | Second response sets `cached` to `true` | `02_api.md` | `PASS` if cache activates |
| `API-009` | Graph endpoint | `Invoke-RestMethod "$Base/graph?search_term=Diabetes" | ConvertTo-Json -Depth 8` | JSON contains `nodes` and `edges` arrays | `02_api.md` | `PASS` if `nodes.Count -gt 0` |
| `API-010` | Non-streaming chat | `$Body = @{message='What are the signs of diabetes?'; session_id=$ClinicianSession} | ConvertTo-Json; Invoke-RestMethod -Method Post "$Base/chat" -ContentType "application/json" -Body $Body | ConvertTo-Json -Depth 8` | JSON contains `response`, `session_id`, `title` | `02_api.md` | `PASS` if `response` is non-empty |
| `API-011` | Patient-mode scope restriction | `$Body = @{message='Write me a Python sorting program'; session_id=$PatientSession; assistant_mode='patient'} | ConvertTo-Json; Invoke-RestMethod -Method Post "$Base/chat" -ContentType "application/json" -Body $Body | ConvertTo-Json -Depth 8` | Response refuses off-topic request and keeps medical scope | `02_api.md` | `PASS` if coding request is blocked |
| `API-012` | SOAP note generation | `$Body = @{session_id=$ClinicianSession; patient_id='10002428'} | ConvertTo-Json; Invoke-RestMethod -Method Post "$Base/soap-note" -ContentType "application/json" -Body $Body | ConvertTo-Json -Depth 8` | JSON contains SOAP note sections | `02_api.md` | `PASS` if note is structured and non-empty |
| `API-013` | Streaming chat SSE | `$Body = @{message='Summarize the risks for patient 10002428'; session_id=$ClinicianSession; patient_id='10002428'} | ConvertTo-Json; curl.exe -N -H "Content-Type: application/json" -d $Body "$Base/chat/stream"` | Multiple `data:` SSE events stream progressively | `02_api.md` | `PASS` if stream returns chunked events |
| `API-014` | Session rename | `$Body = @{session_id=$ClinicianSession; title='Validation Session'} | ConvertTo-Json; Invoke-RestMethod -Method Post "$Base/sessions/rename" -ContentType "application/json" -Body $Body | ConvertTo-Json -Depth 5` | Session title updates successfully | `02_api.md` | `PASS` if renamed session persists |
| `API-015` | Session delete | `Invoke-RestMethod -Method Delete "$Base/sessions/$ClinicianSession" | ConvertTo-Json -Depth 5` | JSON confirms deletion | `02_api.md` | `PASS` if deleted session no longer loads |

---

## Phase 3 - Clinician Workflow Validation

These tests are manual end-to-end validations supported by exact startup commands.

| Test ID | Objective | Setup Command | Manual Steps | Expected Output | Evidence | Outcome Rule |
|---|---|---|---|---|---|---|
| `CLI-001` | Open clinician dashboard | Start backend and frontend using Section 8 commands | Open `http://localhost:5173/clinician` | Dashboard loads without fatal UI error | `03_clinician.md`, screenshots | `PASS` if page is usable |
| `CLI-002` | Create new session | Same runtime | Click `New Chat` or equivalent session action | Session appears in sidebar and is loadable | `03_clinician.md` | `PASS` if session persists |
| `CLI-003` | Load patient data | Same runtime | Select patient `10002428` from sample list | Patient info panel populates with vitals/diagnoses/medications | `03_clinician.md` | `PASS` if data visibly renders |
| `CLI-004` | Send clinician text query | Same runtime | Send `Summarize the current risks for patient 10002428.` | Streaming response appears and final answer is medically scoped | `03_clinician.md` | `PASS` if answer completes |
| `CLI-005` | Generate SOAP note | Same runtime | Use the SOAP note action after a valid chat exchange | Modal opens with structured SOAP output | `03_clinician.md` | `PASS` if note is generated |
| `CLI-006` | Open knowledge graph panel | Same runtime | Trigger a disease-focused query and open graph panel | Graph view displays nodes/edges relevant to current topic | `03_clinician.md` | `PASS` if graph renders |
| `CLI-007` | Image upload flow | Same runtime | Upload `FX-VIS-01` image | Preview appears and uploaded path is accepted by backend | `03_clinician.md` | `PASS` if upload works |
| `CLI-008` | Compound figure flow | Same runtime with `FX-VIS-02` | Upload compound figure and inspect panel analysis UI | Panel viewer shows detected panels when applicable | `03_clinician.md` | `PASS` if panels appear correctly |
| `CLI-009` | Model selection flow | Same runtime | Change text model and vision model selections | New request uses selected model values without UI breakage | `03_clinician.md` | `PASS` if request still completes |
| `CLI-010` | Session reload | Same runtime | Refresh browser and reload saved conversation | Messages persist and reload cleanly | `03_clinician.md` | `PASS` if chat history survives reload |

---

## Phase 4 - Patient Workflow Validation

| Test ID | Objective | Setup Command | Manual Steps / Exact Command | Expected Output | Evidence | Outcome Rule |
|---|---|---|---|---|---|---|
| `PAT-001` | Open patient portal | Start backend and frontend | Open `http://localhost:5173/patient` | Patient portal loads without fatal UI error | `04_patient.md`, screenshots | `PASS` if page is usable |
| `PAT-002` | Load patient summary card | Same runtime | Select patient `10002428` | Summary, vitals, diagnoses, and medications render in patient-friendly language | `04_patient.md` | `PASS` if sections populate |
| `PAT-003` | Validate patient summary endpoint from UI data | `Invoke-RestMethod -Method Post "$Base/patient/10002428/summary" | ConvertTo-Json -Depth 8` | Summary payload uses plain-language structure | `04_patient.md` | `PASS` if summary is understandable and structured |
| `PAT-004` | Validate patient-safe chat | Same runtime | Ask `Can you explain my blood pressure?` | Answer remains patient-friendly and chart-focused | `04_patient.md` | `PASS` if response is scoped and understandable |
| `PAT-005` | Validate off-topic blocking | Same runtime | Ask `Write me a Java program` in patient portal | UI shows refusal aligned with patient scope | `04_patient.md` | `PASS` if off-topic content is blocked |
| `PAT-006` | Validate explain-term path | Same runtime | Request explanation for `tachycardia` from patient UI path | Plain-language explanation appears | `04_patient.md` | `PASS` if explanation is concise and clear |
| `PAT-007` | Validate vitals trend rendering | Same runtime | Inspect vitals charts and hover tooltips | Trend cards and tooltips render without broken values | `04_patient.md` | `PASS` if charts are legible |
| `PAT-008` | Validate medication explanation | Same runtime | Inspect medication section for loaded patient | Medication purpose is translated to plain language | `04_patient.md` | `PASS` if explanations are understandable |
| `PAT-009` | Validate patient session persistence | Same runtime | Refresh page after a short chat | Session reloads and prior messages remain accessible | `04_patient.md` | `PASS` if history persists |

---

## Phase 5 - Core AI and Retrieval Validation

| Test ID | Objective | Exact Command | Expected Output | Evidence | Outcome Rule |
|---|---|---|---|---|---|
| `AI-001` | Context-switch validation | `python .\tests\test_context_switch.py` | Output contains `SUCCESS` checks and no unresolved context bleed | `05_ai_quality.md` | `PASS` if context rewrite behavior is correct |
| `AI-002` | Conversational scenario validation | `python .\tests\test_conversations.py` | Summary report prints scenario results and overall pass count | `05_ai_quality.md` | `PASS` if majority threshold is met and no critical scenario fails |
| `AI-003` | API-level evaluation suite | `python .\tests\test_api_evaluation.py` | Health, graph, medical, patient, drug, vision, and conversation tests run | `05_ai_quality.md` | `PASS` if core suite passes |
| `AI-004` | Comprehensive evaluation suite | `python .\tests\evaluate_system_comprehensive.py` | Extended report generated under `results/` | `05_ai_quality.md`, result files | `PASS` if report is produced without fatal crash |
| `AI-005` | Patient context extraction | `python -c "from src.trustmed_brain import get_patient_context; print(get_patient_context('Assess patient 10002428'))"` | Returns patient-specific context string | `05_ai_quality.md` | `PASS` if output mentions patient data |
| `AI-006` | Direct patient data JSON | `python -c "from src.patient_context_tool import get_patient_data_json; import json; print(json.dumps(get_patient_data_json('10002428'))[:800])"` | JSON-like output contains vitals, diagnoses, medications | `05_ai_quality.md` | `PASS` if structured data exists |
| `AI-007` | Graph JSON generation | `python -c "from src.graph_visualizer import get_graph_json; data=get_graph_json('Diabetes'); print({'nodes':len(data.get('nodes',[])),'edges':len(data.get('edges',[]))})"` | Non-zero node count for valid query | `05_ai_quality.md` | `PASS` if graph data is returned |
| `AI-008` | Explain-term cache behavior | Run `API-007` then `API-008` | First request uncached, second cached | `05_ai_quality.md` | `PASS` if cache path works |
| `AI-009` | Patient scope safety | Run `API-011` | Off-topic coding request is denied | `05_ai_quality.md` | `PASS` if patient scope is enforced |
| `AI-010` | SOAP synthesis quality | Run `API-012` after a clinically relevant chat | SOAP note contains meaningful, non-placeholder sections | `05_ai_quality.md` | `PASS` if note is clinically structured |

---

## Phase 6 - Vision Pipeline Validation

| Test ID | Objective | Exact Command | Expected Output | Evidence | Outcome Rule |
|---|---|---|---|---|---|
| `VIS-001` | Upload single-panel image | `curl.exe -s -X POST -F "file=@tests/fixtures/vision/single_panel_xray.png" "$Base/upload-image"` | JSON contains `path` and original `filename` | `06_vision.md` | `PASS` if file is stored |
| `VIS-002` | Detect single-panel layout | `$Upload = curl.exe -s -X POST -F "file=@tests/fixtures/vision/single_panel_xray.png" "$Base/upload-image" | ConvertFrom-Json; $Body = @{image_path=$Upload.path} | ConvertTo-Json; Invoke-RestMethod -Method Post "$Base/detect-panels" -ContentType "application/json" -Body $Body | ConvertTo-Json -Depth 8` | `is_compound` should be `false` for true single-panel image | `06_vision.md` | `PASS` if result matches fixture expectation |
| `VIS-003` | Upload compound figure | `curl.exe -s -X POST -F "file=@tests/fixtures/vision/compound_figure.png" "$Base/upload-image"` | JSON contains stored file path | `06_vision.md` | `PASS` if upload succeeds |
| `VIS-004` | Detect compound figure | `$Upload = curl.exe -s -X POST -F "file=@tests/fixtures/vision/compound_figure.png" "$Base/upload-image" | ConvertFrom-Json; $Body = @{image_path=$Upload.path} | ConvertTo-Json; Invoke-RestMethod -Method Post "$Base/detect-panels" -ContentType "application/json" -Body $Body | ConvertTo-Json -Depth 8` | `is_compound=true`, `num_panels > 1`, and `panels` array populated | `06_vision.md` | `PASS` if panel list matches expectation |
| `VIS-005` | Validate panel serving | `Invoke-WebRequest "$Base/panels/<panel_filename>" -OutFile ".\validation_runs\$RunId\panel_sample.png"` | Saved panel image file is non-empty | `06_vision.md`, image artifact | `PASS` if image downloads correctly |
| `VIS-006` | Vision cache stats | `Invoke-RestMethod "$Base/vision-cache" | ConvertTo-Json -Depth 5` | JSON contains `hits`, `misses`, `cached_images`, `max_size` | `06_vision.md` | `PASS` if cache stats endpoint responds |
| `VIS-007` | Clear vision cache | `Invoke-RestMethod -Method Post "$Base/vision-cache/clear" | ConvertTo-Json -Depth 5` | Cache clear confirmation is returned | `06_vision.md` | `PASS` if clear succeeds |
| `VIS-008` | Full vision API evaluation | `python .\tests\test_api_evaluation.py` | Vision portion of suite passes or is explicitly blocked by fixture absence | `06_vision.md` | `PASS` if vision stage behaves as expected |

---

## Phase 7 - Data and Ingestion Validation

| Test ID | Objective | Exact Command | Expected Output | Evidence | Outcome Rule |
|---|---|---|---|---|---|
| `DAT-001` | Validate SQLite access | `python -c "import sqlite3; conn=sqlite3.connect(r'data\\mimic_demo.db'); print(conn.execute('select count(*) from diagnosis').fetchone()[0])"` | Positive integer row count | `07_data.md` | `PASS` if count is greater than 0 |
| `DAT-002` | Validate patient table usefulness | `python -c "from src.patient_context_tool import get_patient_data_json; data=get_patient_data_json('10002428'); print(bool(data.get('vitals') or data.get('diagnoses') or data.get('medications')))"` | `True` | `07_data.md` | `PASS` if patient data exists |
| `DAT-003` | Validate Chroma collections | `python -c "import chromadb; client=chromadb.PersistentClient(path='data/chroma_db'); print([c.name for c in client.list_collections()])"` | Non-empty collection list | `07_data.md` | `PASS` if at least one collection exists |
| `DAT-004` | Validate legacy Chroma path assumptions | `python .\tests\verify_new_db.py` | Script either passes or clearly documents path mismatch | `07_data.md` | `PASS` if output is explained and actionable |
| `DAT-005` | Validate Neo4j graph path | `python -c "from src.graph_visualizer import get_graph_json; data=get_graph_json('Asthma'); print(type(data).__name__, len(data.get('nodes',[])))"` | Dict-like output with nodes array | `07_data.md` | `PASS` if graph data returns |
| `DAT-006` | Validate ingestion scripts compile | `python -m compileall .\ingestion` | No compile failures | `07_data.md` | `PASS` if exit code is 0 |
| `DAT-007` | Validate schema config presence | `Test-Path ".\ingestion\schema_config.yaml"` | `True` | `07_data.md` | `PASS` if file exists |
| `DAT-008` | Validate runtime persistence folders | `Test-Path ".\chat_history"; Test-Path ".\uploads"` | Both paths return `True` after backend startup | `07_data.md` | `PASS` if both runtime folders exist |

---

## Phase 8 - Performance and Resilience Validation

| Test ID | Objective | Exact Command | Expected Output | Evidence | Outcome Rule |
|---|---|---|---|---|---|
| `PERF-001` | Root latency smoke | `Measure-Command { Invoke-RestMethod "$Base/" | Out-Null }` | Root request completes in well under 1 second locally | `08_performance.md` | `PASS` if local root latency is acceptable |
| `PERF-002` | Patient endpoint latency | `Measure-Command { Invoke-RestMethod "$Base/patient/10002428" | Out-Null }` | Patient lookup completes quickly and consistently | `08_performance.md` | `PASS` if repeated runs are stable |
| `PERF-003` | Extensive performance suite | `python .\tests\performance_test_extensive.py` | Stress, concurrency, and latency breakdown reports are produced | `08_performance.md`, result files | `PASS` if suite runs to completion |
| `PERF-004` | API evaluation under realistic flow | `python .\tests\test_api_evaluation.py` | End-to-end suite completes with stable latencies | `08_performance.md` | `PASS` if no endpoint crashes |
| `PERF-005` | Session persistence under reload | Perform `CLI-010` and `PAT-009` after multiple interactions | Session files remain readable and reloadable | `08_performance.md` | `PASS` if persistence is stable |
| `PERF-006` | No runaway cache growth | `Invoke-RestMethod "$Base/vision-cache" | ConvertTo-Json -Depth 5` after repeated image tests | `cached_images` remains bounded by configured max size | `08_performance.md` | `PASS` if cache stays within limits |

Suggested acceptance thresholds, aligned to current project docs:

- Chat success rate: `>= 95%`
- Context-switch correctness: `>= 90%`
- Core API availability: `100%` for health/session/patient endpoints
- Frontend lint/build: `100%`
- Root endpoint latency: `< 500 ms` local target
- Performance suite completion without crash: required

---

## Phase 9 - Legacy Surface Validation

| Test ID | Objective | Exact Command | Expected Output | Evidence | Outcome Rule |
|---|---|---|---|---|---|
| `LEG-001` | Legacy Streamlit import smoke | `python -c "import app; print('streamlit_import_ok')"` | `streamlit_import_ok` | `09_legacy.md` | `PASS` if import works |
| `LEG-002` | Legacy runtime status | `streamlit run .\app.py` | App starts or failure is documented as intentional legacy drift | `09_legacy.md` | `PASS` if status is explicitly documented |

If the project no longer intends to support the Streamlit path, mark the phase `NOT RUN` and state that the current validated surface is FastAPI + Next.js only.

---

## Phase 10 - Release and Signoff Validation

| Test ID | Objective | Exact Command / Step | Expected Output | Evidence | Outcome Rule |
|---|---|---|---|---|---|
| `REL-001` | Confirm artifact completeness | Verify `validation_runs/<RunId>/` contains all phase reports | Full evidence bundle exists | `10_signoff.md` | `PASS` if bundle is complete |
| `REL-002` | Confirm blockers are enumerated | Summarize all `FAIL` and `BLOCKED` results | Defect list is explicit and prioritized | `10_signoff.md` | `PASS` if no silent failures remain |
| `REL-003` | Rerun smoke subset | Rerun `ENV-004`, `STA-001`, `API-001`, `API-005`, `API-010`, `AI-001` | Key smoke tests remain stable after fixes | `10_signoff.md` | `PASS` if smoke subset passes |
| `REL-004` | Final release decision | Apply decision rubric below | Final status is `GO`, `GO WITH RISKS`, or `NO-GO` | `10_signoff.md` | Required |

### Release Decision Rubric

- `GO`: No critical failures, no unresolved blockers for active product path
- `GO WITH RISKS`: Non-critical failures exist but are documented and accepted
- `NO-GO`: Core workflow, patient safety scope, or backend contract is broken or blocked

## 10. Recommended Validation Execution Sequence

Use the following exact high-level run order:

```powershell
Set-Location "C:\ASU\Sem 4\code\TrustMed-AI"
$RunId = Get-Date -Format "yyyyMMdd_HHmmss"
New-Item -ItemType Directory -Force -Path ".\validation_runs\$RunId" | Out-Null
```

Then execute in this order:

1. `ENV-*`
2. `STA-*`
3. Start backend
4. Start frontend
5. `API-*`
6. `CLI-*`
7. `PAT-*`
8. `AI-*`
9. `VIS-*`
10. `DAT-*`
11. `PERF-*`
12. `LEG-*`
13. `REL-*`

## 11. Reporting Templates

### 11.1 Master Validation Summary Template

```markdown
# Validation Summary

- Run ID:
- Date:
- Validator:
- Commit SHA:
- Environment:
- Backend URL:
- Frontend URL:
- Overall Decision: GO / GO WITH RISKS / NO-GO

## Phase Status

| Phase | Status | Passed | Failed | Blocked | Notes |
|---|---|---:|---:|---:|---|
| 00 Preflight |  |  |  |  |  |
| 01 Static |  |  |  |  |  |
| 02 API |  |  |  |  |  |
| 03 Clinician |  |  |  |  |  |
| 04 Patient |  |  |  |  |  |
| 05 AI Quality |  |  |  |  |  |
| 06 Vision |  |  |  |  |  |
| 07 Data |  |  |  |  |  |
| 08 Performance |  |  |  |  |  |
| 09 Legacy |  |  |  |  |  |
| 10 Signoff |  |  |  |  |  |
```

### 11.2 Detailed Test Result Template

```markdown
## <TEST-ID> - <TITLE>

- Phase:
- Objective:
- Preconditions:
- Type: Automated / Manual / Hybrid
- Exact Command or Step:
- Expected Output:
- Actual Output:
- Status: PASS / FAIL / BLOCKED / NOT RUN
- Evidence Files:
- Notes / Root Cause:
```

### 11.3 Defect Log Template

```markdown
## Defect <DEFECT-ID>

- Linked Test ID:
- Severity: Critical / High / Medium / Low
- Summary:
- Reproduction:
- Expected:
- Actual:
- Evidence:
- Suspected Area:
- Owner:
- Status:
```

### 11.4 Reproducibility Manifest Template

```markdown
# Reproducibility Manifest

- Run ID:
- Commit SHA:
- Python Version:
- Node Version:
- npm Version:
- OS:
- Time Zone:
- `.env` present: Yes / No
- SQLite DB present: Yes / No
- Chroma DB present: Yes / No
- Neo4j reachable: Yes / No
- Fixtures present:
  - FX-PAT-01:
  - FX-VIS-01:
  - FX-VIS-02:
- Backend start command:
- Frontend start command:
```

### 11.5 Signoff Template

```markdown
# Final Signoff

- Run ID:
- Decision: GO / GO WITH RISKS / NO-GO
- Validated Surface:
- Core Risks:
- Blockers:
- Waived Issues:
- Recommended Next Actions:
- Approved By:
```

## 12. Expected Deliverables from a Full Validation Run

At the end of a formal run, the following should exist:

- `validation_runs/<RunId>/00_preflight.md`
- `validation_runs/<RunId>/01_static.md`
- `validation_runs/<RunId>/02_api.md`
- `validation_runs/<RunId>/03_clinician.md`
- `validation_runs/<RunId>/04_patient.md`
- `validation_runs/<RunId>/05_ai_quality.md`
- `validation_runs/<RunId>/06_vision.md`
- `validation_runs/<RunId>/07_data.md`
- `validation_runs/<RunId>/08_performance.md`
- `validation_runs/<RunId>/09_legacy.md`
- `validation_runs/<RunId>/10_signoff.md`
- Raw command outputs, screenshots, exported JSON reports, and copied result files

## 13. Current Known Validation Risks

Based on the current repository state observed during planning:

- `.env` is not present in the current checkout
- `data/` is not present in the current checkout
- `chat_history/` and `uploads/` are runtime-generated and may not exist until backend import/startup
- Some documentation and older scripts reference older paths such as `./chroma_db`
- The Streamlit app still exists as a legacy path and should be validated separately from the main product

These do not invalidate the plan, but they do affect whether a given execution is marked `PASS`, `FAIL`, or `BLOCKED`.

## 14. Final Usage Note

This document is the master validation blueprint. It is intended to be used unchanged as the reference plan for repeated runs, while the files under `validation_runs/` hold the actual per-run evidence and outcomes.
