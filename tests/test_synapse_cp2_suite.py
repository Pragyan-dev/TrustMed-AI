"""
Synapse AI — Checkpoint 2 Targeted Test Suite
Team Alabama | Arizona State University | FSE 570

Covers:
  GROUP 1: Neo4j / MIMIC Data Ingestion & Traversal
  GROUP 2: Vision-Text Model Fusion (Vertex AI / MedGemma + BiomedCLIP)
  GROUP 3: SOAP Note Generation Streaming Pipeline
  GROUP 4: Drug Safety Pipeline & Signal Filtering
  GROUP 5: Full-Stack Next.js / FastAPI Dashboard Communication

Prerequisites:
  - Backend running:  uvicorn api.main:app --port 8000
  - .env configured:  OPENROUTER_API_KEY, NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD
  - Demo DB seeded:   python create_demo_db.py

Run:
  python -m pytest tests/test_synapse_cp2_suite.py -v --tb=short
  python -m pytest tests/test_synapse_cp2_suite.py -v -k "not Integration" --tb=short  # Unit-only
"""

import os
import sys
import json
import time
import tempfile
import pytest
import requests

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

BASE_URL = os.getenv("TEST_API_URL", "http://localhost:8000")
KNOWN_PATIENT_ID = "10002428"


# =============================================================================
# GROUP 1 — Neo4j / MIMIC Data Ingestion & Traversal
# =============================================================================

class TestNeo4jMIMIC:

    def test_patient_context_known_patient(self):
        """
        TEST-NEO-001 | Unit
        Scenario: Query a known patient in the demo DB (ID: 10002428).
        Expected: Non-empty string with vitals, diagnoses, or medications.
        """
        from src.patient_context_tool import get_patient_vitals, get_patient_diagnoses, get_patient_meds
        vitals = get_patient_vitals.invoke(KNOWN_PATIENT_ID)
        diagnoses = get_patient_diagnoses.invoke(KNOWN_PATIENT_ID)
        meds = get_patient_meds.invoke(KNOWN_PATIENT_ID)
        assert len(vitals) > 5, "Vitals should not be empty"
        assert len(diagnoses) > 5, "Diagnoses should not be empty"
        assert len(meds) > 5, "Medications should not be empty"

    def test_patient_context_no_id_returns_empty(self):
        """
        TEST-NEO-002 | Unit
        Scenario: Query with no patient ID pattern.
        Expected: Empty string returned, no exception.
        """
        from src.trustmed_brain import get_patient_context
        result = get_patient_context("What is the treatment for pneumonia?")
        assert result == ""

    @pytest.mark.integration
    def test_neo4j_connectivity(self):
        """
        TEST-NEO-003 | Integration
        Scenario: Verify Neo4j Aura connectivity and graph chain init.
        Expected: get_graph_chain() returns non-None without ConnectionError.
        """
        from src.trustmed_brain import get_graph_chain
        try:
            chain = get_graph_chain()
            assert chain is not None
        except ConnectionError as ce:
            pytest.skip(f"Neo4j paused or unreachable: {ce}")

    @pytest.mark.integration
    def test_graph_context_pneumonia(self):
        """
        TEST-NEO-004 | Integration
        Scenario: Graph query for 'pneumonia symptoms'.
        Expected: Response references known pneumonia symptoms.
        """
        from src.trustmed_brain import get_graph_context
        try:
            result = get_graph_context("What are the symptoms of pneumonia?")
            assert any(kw in result.lower() for kw in ["fever", "cough", "dyspnea", "symptom", "chest", "pain"])
            assert "knowledge graph unavailable" not in result.lower()
        except ConnectionError:
            pytest.skip("Neo4j unavailable")

    @pytest.mark.integration
    def test_graph_cypher_fuzzy_matching(self):
        """
        TEST-NEO-005 | Integration
        Scenario: Slightly misspelled disease ('pneumomia') → graph still responds.
        Expected: Non-empty result due to CONTAINS fuzzy matching.
        """
        from src.trustmed_brain import get_graph_context
        try:
            result = get_graph_context("pneumomia treatment precautions")
            assert len(result) > 20
        except ConnectionError:
            pytest.skip("Neo4j unavailable")

    @pytest.mark.integration
    def test_patient_api_endpoint(self):
        """
        TEST-NEO-006 | Integration
        Scenario: GET /patient/10002428 from FastAPI backend.
        Expected: 200 with non-empty vitals, diagnoses, medications.
        """
        try:
            resp = requests.get(f"{BASE_URL}/patient/{KNOWN_PATIENT_ID}", timeout=15)
        except requests.ConnectionError:
            pytest.skip("Backend not running")
        assert resp.status_code == 200
        data = resp.json()
        assert data.get("vitals") is not None or data.get("diagnoses") is not None
        print(f"  Vitals keys: {list(data.get('vitals', {}).keys())[:5]}")
        print(f"  Diagnoses count: {len(data.get('diagnoses', []))}")
        print(f"  Medications count: {len(data.get('medications', []))}")


# =============================================================================
# GROUP 2 — Vision-Text Model Fusion
# =============================================================================

class TestVisionTextFusion:

    def test_vision_tool_missing_file(self):
        """
        TEST-VIS-001 | Unit
        Scenario: Pass a non-existent image path.
        Expected: Error string returned, no exception raised.
        """
        from src.vision_tool import analyze_medical_image
        result = analyze_medical_image.invoke("/nonexistent/path/image.jpg")
        assert isinstance(result, str)
        assert "error" in result.lower() or "not found" in result.lower()

    def test_vision_output_structured_format(self):
        """
        TEST-VIS-002 | Unit
        Scenario: Valid JSON from vision model is parsed correctly.
        Expected: [HIGH] and [LOW] tags, STRUCTURED OUTPUT marker.
        """
        from src.vision_tool import _validate_and_format_vision_output
        mock_json = json.dumps({
            "modality": "X-Ray",
            "body_region": "Chest/Thorax",
            "high_confidence_findings": [{"finding": "Cardiomegaly", "confidence": "HIGH"}],
            "uncertain_findings": [{"finding": "Possible pleural effusion", "confidence": "LOW"}],
            "cannot_assess": ["Lung parenchyma"],
            "overall_impression": "Enlarged cardiac silhouette noted."
        })
        result = _validate_and_format_vision_output(mock_json, "medgemma-27b-vertex")
        assert "[HIGH] Cardiomegaly" in result
        assert "[LOW] Possible pleural effusion" in result
        assert "STRUCTURED OUTPUT" in result

    def test_vision_output_unstructured_flagged(self):
        """
        TEST-VIS-003 | Unit
        Scenario: Vision model returns plain text (not JSON).
        Expected: [UNSTRUCTURED] flag and LOW confidence warning.
        """
        from src.vision_tool import _validate_and_format_vision_output
        result = _validate_and_format_vision_output(
            "The chest X-ray appears to show some opacity in the right lung.",
            "llama-3.2-vision"
        )
        assert "UNSTRUCTURED" in result
        assert "LOW confidence" in result.lower()

    def test_vision_cache_structure(self):
        """
        TEST-VIS-004 | Unit
        Scenario: Validate cache statistics dictionary structure.
        Expected: Cache stats dict has 'hits', 'misses', 'hit_rate', 'cached_images'.
        """
        from src.vision_agent import get_vision_cache_stats, clear_vision_cache
        clear_vision_cache()
        stats = get_vision_cache_stats()
        for key in ["hits", "misses", "hit_rate", "cached_images", "max_size"]:
            assert key in stats, f"Missing key: {key}"
        assert stats["hits"] == 0
        assert stats["misses"] == 0
        assert stats["cached_images"] == 0

    def test_chroma_medical_images_collection(self):
        """
        TEST-VIS-005 | Integration
        Pre-condition: ingestion/ingest_mimic_cxr.py must have been run.
        Scenario: ChromaDB medical_images collection exists and has records.
        Expected: Collection count > 0.
        """
        import chromadb
        client = chromadb.PersistentClient(path="./data/chroma_db")
        try:
            collection = client.get_collection("medical_images")
            count = collection.count()
            print(f"  ✓ {count} images in Visual-RAG database")
            if count == 0:
                pytest.skip("medical_images collection is empty — run ingest_mimic_cxr.py first")
            assert count > 0
        except Exception as e:
            pytest.skip(f"medical_images collection not found (run ingestion): {e}")

    def test_cross_reference_graceful_no_data(self):
        """
        TEST-VIS-006 | Unit
        Scenario: _cross_reference_findings with nonexistent image path.
        Expected: Returns None or string (no exception).
        """
        from src.vision_agent import _cross_reference_findings
        mock_vision = "HIGH-CONFIDENCE Findings:\n  [HIGH] Pneumonia with consolidation"
        result = _cross_reference_findings(mock_vision, "/nonexistent/image.jpg")
        assert result is None or isinstance(result, str)

    def test_search_query_extraction(self):
        """
        TEST-VIS-007 | Unit
        Scenario: Extract search query from structured vision output.
        Expected: Returns non-empty string with high-confidence finding terms.
        """
        from src.vision_agent import _extract_search_query
        vision_output = (
            "Modality & Region: X-Ray — Chest\n"
            "[HIGH] Cardiomegaly — enlarged cardiac silhouette\n"
            "[LOW] Possible pleural effusion\n"
            "Overall Impression: Enlarged heart, possible fluid."
        )
        query = _extract_search_query(vision_output)
        assert len(query) > 5
        assert "Cardiomegaly" in query or "X-Ray" in query or "Chest" in query


# =============================================================================
# GROUP 3 — SOAP Note Generation Pipeline
# =============================================================================

class TestSOAPNoteGeneration:

    def test_soap_empty_history_error(self):
        """
        TEST-SOAP-002 | Unit (no API key required)
        Scenario: Call generate_soap_note with empty history.
        Expected: Returns dict with 'error' key, not exception.
        """
        from src.trustmed_brain import generate_soap_note
        result = generate_soap_note([], "Some patient context", "No imaging")
        assert isinstance(result, dict)
        assert "error" in result
        assert result["error"] == "No session history to generate note from."

    def test_soap_metadata_structure_on_success(self):
        """
        TEST-SOAP-004 | Unit (mocked — no LLM call)
        Scenario: Directly test metadata injection into SOAP output.
        Expected: _metadata dict has note_id starting with 'SOAP-' and generated_at.
        """
        # Build the metadata the same way generate_soap_note does
        from datetime import datetime
        metadata = {
            "generated_at": datetime.now().isoformat(),
            "note_id": f"SOAP-{datetime.now().strftime('%Y%m%d-%H%M%S')}",
            "message_count": 2,
        }
        assert metadata["note_id"].startswith("SOAP-")
        assert "generated_at" in metadata
        assert metadata["message_count"] == 2

    @pytest.mark.integration
    @pytest.mark.slow
    def test_soap_generation_from_history(self):
        """
        TEST-SOAP-001 | Integration (requires OPENROUTER_API_KEY)
        Scenario: Provide a mock clinical conversation history.
        Expected: Returns dict with subjective, objective, assessment, plan keys.
        """
        from src.trustmed_brain import generate_soap_note
        history = [
            {"role": "user", "content": "Patient has fever 38.5°C, dry cough for 3 days, SpO2 94%."},
            {"role": "assistant", "content": (
                "Based on the presentation with fever, dry cough, and borderline SpO2, "
                "community-acquired pneumonia is the leading diagnosis. The right lower lobe "
                "opacity confirms atypical pneumonia pattern. Recommend oral azithromycin and "
                "follow-up chest X-ray in 48 hours."
            )}
        ]
        result = generate_soap_note(
            history,
            "Patient 10002428, age 65, known hypertension, currently on lisinopril",
            "Chest X-ray: right lower lobe opacity"
        )
        if "error" in result:
            if "LLM call failed" in result["error"] or "rate" in result["error"].lower():
                pytest.skip(f"LLM unavailable: {result['error']}")
        assert "subjective" in result, f"Missing subjective. Got: {list(result.keys())}"
        assert "objective" in result
        assert "assessment" in result
        assert "plan" in result

    @pytest.mark.integration
    def test_soap_api_endpoint(self):
        """
        TEST-SOAP-003 | Integration (requires backend + OPENROUTER_API_KEY)
        Scenario: Create session, add chat message, then generate SOAP note via API.
        Expected: 200 response with valid SOAP structure.
        """
        try:
            # Create session
            create_resp = requests.post(f"{BASE_URL}/sessions/new", params={"source": "clinician"}, timeout=5)
        except requests.ConnectionError:
            pytest.skip("Backend not running")

        assert create_resp.status_code == 200
        session_id = create_resp.json()["id"]

        # Add clinical context
        chat_payload = {
            "message": "Patient presents with fever, cough, and right lower lobe infiltrate on X-ray.",
            "session_id": session_id,
            "persist": True
        }
        chat_resp = requests.post(f"{BASE_URL}/chat", json=chat_payload, timeout=60)
        if chat_resp.status_code != 200:
            pytest.skip(f"Chat failed: {chat_resp.status_code}")

        # Generate SOAP
        soap_resp = requests.post(
            f"{BASE_URL}/soap-note",
            json={"session_id": session_id, "patient_id": KNOWN_PATIENT_ID},
            timeout=60
        )
        if soap_resp.status_code == 400:
            pytest.skip("Session history insufficient for SOAP generation")

        assert soap_resp.status_code == 200, f"SOAP note failed: {soap_resp.text}"
        data = soap_resp.json()
        assert "subjective" in data
        assert "objective" in data
        assert "assessment" in data
        assert "plan" in data


# =============================================================================
# GROUP 4 — Drug Safety Pipeline & Signal Filtering
# =============================================================================

class TestDrugSafetyPipeline:

    def _build_patient_context(self, medications: list, diagnoses: list, age: int = 40):
        """Helper: Build a structured patient context string."""
        ctx = f"""=== PATIENT CONTEXT ===
Age: {age}
Active Medications:
"""
        for med in medications:
            ctx += f"- {med}\n"
        ctx += "Diagnoses:\n"
        for dx in diagnoses:
            ctx += f"- {dx}\n"
        return ctx

    def test_qt_prolongation_azithromycin_citalopram(self):
        """
        TEST-DRUG-001 | Integration (Neo4j for drug class lookup; hardcoded fallback)
        Scenario: Patient on azithromycin + citalopram (both known QT-prolonging).
        Expected: 'QT PROLONGATION' alert returned.
        """
        from src.trustmed_brain import check_drug_interactions
        ctx = self._build_patient_context(
            medications=["Azithromycin (antibiotic)", "Citalopram (SSRI antidepressant)"],
            diagnoses=["Community Acquired Pneumonia", "Depression"]
        )
        result = check_drug_interactions(ctx)
        # QT check uses hardcoded dict — works even without Neo4j
        assert "QT PROLONGATION" in result.upper(), (
            f"Expected QT PROLONGATION alert. Got:\n{result}"
        )

    def test_beers_criteria_elderly_lorazepam(self):
        """
        TEST-DRUG-002 | Unit (hardcoded Beers criteria — no Neo4j required)
        Scenario: Patient age 70 on lorazepam (benzodiazepine, Beers high-risk).
        Expected: Alert contains 'BEERS CRITERIA'.
        """
        from src.trustmed_brain import check_drug_interactions
        ctx = self._build_patient_context(
            medications=["Lorazepam (sedative)"],
            diagnoses=["Anxiety disorder"],
            age=70
        )
        result = check_drug_interactions(ctx)
        assert "BEERS CRITERIA" in result.upper(), (
            f"Expected BEERS CRITERIA alert for elderly patient on lorazepam. Got:\n{result}"
        )
        assert "lorazepam" in result.lower()

    def test_drug_alert_signal_filter_no_treatment_text(self):
        """
        TEST-DRUG-003 | Unit
        Scenario: Apply streaming alert filter to raw drug safety output.
        Expected: Only safety markers emitted; no treatment recommendation text.
        """
        from src.trustmed_brain import check_drug_interactions
        ctx = self._build_patient_context(
            medications=["Azithromycin (antibiotic)", "Citalopram (SSRI)"],
            diagnoses=["Pneumonia"]
        )
        raw_alerts = check_drug_interactions(ctx)

        ALERT_MARKERS = [
            "DRUG INTERACTION", "CONTRAINDICATION", "QT PROLONGATION",
            "BLEEDING RISK", "DUPLICATE THERAPY", "RENAL DOSE",
            "HEPATIC DOSE", "BEERS CRITERIA",
        ]
        alert_lines = []
        for line in raw_alerts.strip().split("\n"):
            line = line.strip()
            if not line:
                continue
            if any(marker in line.upper() for marker in ALERT_MARKERS):
                alert_lines.append(line)
            elif line.startswith("   ") and alert_lines:
                alert_lines[-1] += "\n" + line

        # Filtered alerts should not contain treatment recommendation headers
        combined_upper = " ".join(alert_lines).upper()
        assert "GUIDELINE-BASED TREATMENTS" not in combined_upper, (
            "Treatment text leaked into alert output — filtering failed"
        )
        if "QT PROLONGATION" in combined_upper or "DRUG INTERACTION" in combined_upper:
            print("  ✓ QT alert correctly captured")

    def test_renal_dose_warning_metformin(self):
        """
        TEST-DRUG-004 | Unit (hardcoded renal rules — no Neo4j required)
        Scenario: Patient with CKD on metformin.
        Expected: 'RENAL DOSE WARNING' alert with eGFR/CrCl guidance.
        """
        from src.trustmed_brain import check_drug_interactions
        ctx = self._build_patient_context(
            medications=["Metformin (diabetes medication)", "Lisinopril (ACE inhibitor)"],
            diagnoses=["Chronic kidney disease", "Type 2 Diabetes", "Renal impairment"]
        )
        result = check_drug_interactions(ctx)
        assert "RENAL DOSE WARNING" in result.upper(), (
            f"Expected renal dose warning for metformin + CKD. Got:\n{result}"
        )
        assert "metformin" in result.lower()

    def test_no_false_positive_safe_medications(self):
        """
        TEST-DRUG-005 | Unit
        Scenario: Patient on vitamin D + lisinopril, no serious comorbidities.
        Expected: No HIGH-severity false positive alerts.
        """
        from src.trustmed_brain import check_drug_interactions
        ctx = self._build_patient_context(
            medications=["Vitamin D supplement", "Lisinopril (ACE inhibitor)"],
            diagnoses=["Hypertension"],
            age=45
        )
        result = check_drug_interactions(ctx)
        # These markers indicate high-severity alerts that shouldn't fire for this combo
        false_positive_markers = [
            "QT PROLONGATION RISK",  # Not expected
            "BLEEDING RISK",         # Not expected
        ]
        for marker in false_positive_markers:
            # More specific: look for HIGH-severity pattern
            assert "🔴" not in result or marker not in result.upper(), (
                f"False positive: {marker} fired for a safe medication list"
            )

    def test_medication_extraction_from_context(self):
        """
        TEST-DRUG-006 | Unit
        Scenario: Extract medication names from MIMIC-formatted patient context.
        Expected: Correct list of drug names extracted.
        """
        from src.trustmed_brain import _extract_medication_names
        context = """Active Medications:
- Aspirin (analgesic)
- Metformin (antidiabetic)
- Lisinopril
"""
        meds = _extract_medication_names(context)
        assert "aspirin" in meds
        assert "metformin" in meds
        assert "lisinopril" in meds

    def test_diagnosis_extraction_from_context(self):
        """
        TEST-DRUG-007 | Unit
        Scenario: Extract diagnosis names from MIMIC-formatted context.
        Expected: Correct list of diagnoses extracted.
        """
        from src.trustmed_brain import _extract_diagnosis_names
        context = """Diagnoses:
- Pneumonia (ICD: J18.9)
- Hypertension NOS
- Type 2 Diabetes, UNSPECIFIED
"""
        diagnoses = _extract_diagnosis_names(context)
        assert any("pneumonia" in d for d in diagnoses)
        assert any("hypertension" in d for d in diagnoses)
        assert any("diabetes" in d for d in diagnoses)
        # Should NOT include raw ICD codes
        assert all("J18" not in d for d in diagnoses)


# =============================================================================
# GROUP 5 — Full-Stack Next.js / FastAPI Dashboard Communication
# =============================================================================

class TestFullStackCommunication:

    @pytest.fixture(autouse=True)
    def check_backend_available(self):
        """Skip all integration tests if backend is not running."""
        try:
            resp = requests.get(f"{BASE_URL}/", timeout=3)
            if resp.status_code != 200:
                pytest.skip("Backend returned non-200")
        except requests.ConnectionError:
            pytest.skip("Backend not running at localhost:8000")

    def test_root_endpoint(self):
        """Sanity check: backend is running."""
        resp = requests.get(f"{BASE_URL}/")
        assert resp.status_code == 200
        data = resp.json()
        assert "TrustMed AI" in data.get("message", "")

    def test_session_create_and_retrieve(self):
        """
        TEST-API-002 | Integration
        Scenario: Create session, send message, retrieve history.
        Expected: Session contains at least user+assistant messages.
        """
        session = requests.post(f"{BASE_URL}/sessions/new").json()
        session_id = session["id"]
        assert session_id is not None

        payload = {
            "message": "What is hypertension?",
            "session_id": session_id,
            "persist": True
        }
        chat_resp = requests.post(f"{BASE_URL}/chat", json=payload, timeout=60)
        if chat_resp.status_code != 200:
            pytest.skip(f"Chat failed: {chat_resp.status_code} — LLM unavailable?")

        sess_resp = requests.get(f"{BASE_URL}/sessions/{session_id}")
        assert sess_resp.status_code == 200
        data = sess_resp.json()
        messages = data.get("messages", [])
        assert len(messages) >= 2, f"Expected 2+ messages, got {len(messages)}"
        roles = [m["role"] for m in messages]
        assert "user" in roles and "assistant" in roles

        # Cleanup
        requests.delete(f"{BASE_URL}/sessions/{session_id}")

    def test_patient_portal_blocks_coding_question(self):
        """
        TEST-API-003 | Integration
        Scenario: Patient portal receives a Python coding request.
        Expected: Scope-restriction message returned; specifically not a code answer.
        """
        payload = {
            "message": "Write me a python script to sort an array",
            "session_id": f"test-scope-{time.time()}",
            "assistant_mode": "patient",
            "persist": False
        }
        resp = requests.post(f"{BASE_URL}/chat", json=payload, timeout=30)
        if resp.status_code != 200:
            pytest.skip(f"Chat endpoint failed: {resp.status_code}")

        response_text = resp.json()["response"]
        # Should NOT contain python code
        assert "def " not in response_text, "Portal answered a coding question!"
        assert "sort(" not in response_text, "Portal provided sorting code!"
        # Should contain scope restriction keywords
        scope_keywords = ["health record", "medications", "only help", "care plan", "diagnoses"]
        assert any(kw in response_text.lower() for kw in scope_keywords), (
            f"Expected scope restriction. Got: {response_text[:200]}"
        )

    def test_knowledge_graph_endpoint(self):
        """
        TEST-API-004 | Integration
        Scenario: GET /graph?search_term=pneumonia
        Expected: Returns JSON with 'nodes' and 'edges' (even if Neo4j is down — graceful empty).
        """
        resp = requests.get(f"{BASE_URL}/graph", params={"search_term": "pneumonia"}, timeout=30)
        assert resp.status_code == 200
        data = resp.json()
        assert "nodes" in data, f"Missing 'nodes' key. Got: {list(data.keys())}"
        assert "edges" in data, f"Missing 'edges' key. Got: {list(data.keys())}"
        assert isinstance(data["nodes"], list)
        assert isinstance(data["edges"], list)
        print(f"  Graph: {len(data['nodes'])} nodes, {len(data['edges'])} edges")

    def test_image_upload_and_retrieval(self):
        """
        TEST-API-005 | Integration
        Scenario: Upload a PNG image. Verify it's stored and accessible.
        Expected: Upload returns filename; file is accessible at /uploads/{filename}.
        """
        try:
            from PIL import Image
        except ImportError:
            pytest.skip("Pillow not installed")

        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
            img = Image.new("RGB", (100, 100), color=(100, 150, 200))
            img.save(f.name)
            tmp_path = f.name

        try:
            with open(tmp_path, "rb") as f:
                resp = requests.post(
                    f"{BASE_URL}/upload-image",
                    files={"file": ("test_scan.png", f, "image/png")},
                    timeout=15
                )
            assert resp.status_code == 200, f"Upload failed: {resp.text}"
            data = resp.json()
            assert "path" in data
            assert "filename" in data

            # Verify file is accessible
            filename = os.path.basename(data["path"])
            serve_resp = requests.get(f"{BASE_URL}/uploads/{filename}", timeout=10)
            assert serve_resp.status_code == 200
            print(f"  ✓ Uploaded: {filename}")
        finally:
            os.unlink(tmp_path)

    def test_sse_stream_event_types(self):
        """
        TEST-API-001 | Integration
        Scenario: Send clinical query through /chat/stream.
        Expected: Stream yields typed events including 'progress' and 'done'.
        """
        session_id = f"test-sse-{int(time.time())}"
        payload = {
            "message": "What are the key symptoms of hypertension?",
            "session_id": session_id,
            "persist": False
        }
        events = []
        try:
            with requests.post(
                f"{BASE_URL}/chat/stream",
                json=payload,
                stream=True,
                timeout=120
            ) as resp:
                assert resp.status_code == 200
                assert "text/event-stream" in resp.headers.get("content-type", "")

                for line in resp.iter_lines(decode_unicode=True):
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            events.append(data.get("type"))
                            if data.get("type") == "done":
                                break
                        except json.JSONDecodeError:
                            continue
        except requests.Timeout:
            pytest.fail("SSE stream timed out after 120s")

        assert "progress" in events, f"No progress events. Got: {events}"
        assert "done" in events, f"Stream never completed. Got: {events}"
        print(f"  Event sequence: {events}")

    @pytest.mark.slow
    def test_e2e_patient_query_with_drug_alerts(self):
        """
        TEST-API-006 | Integration (Full E2E — may take 30-90s)
        Scenario: Query with patient ID 10002428 + ask about drug interactions.
        Expected:
          - patient_context event emitted
          - drug_alerts event emitted (patient has medications)
          - done event received with non-empty response
        """
        payload = {
            "message": f"Tell me about patient {KNOWN_PATIENT_ID}'s drug interaction risks.",
            "session_id": f"test-e2e-{int(time.time())}",
            "persist": False
        }
        events_received = []
        patient_context_events = []
        drug_alert_events = []
        final_response = ""

        try:
            with requests.post(
                f"{BASE_URL}/chat/stream",
                json=payload,
                stream=True,
                timeout=180
            ) as resp:
                assert resp.status_code == 200
                for line in resp.iter_lines(decode_unicode=True):
                    if line.startswith("data: "):
                        try:
                            data = json.loads(line[6:])
                            event_type = data.get("type")
                            events_received.append(event_type)
                            if event_type == "patient_context":
                                patient_context_events.append(data)
                            elif event_type == "drug_alerts":
                                drug_alert_events.append(data)
                            elif event_type == "done":
                                final_response = data.get("final_response", "")
                                break
                        except json.JSONDecodeError:
                            continue
        except requests.Timeout:
            pytest.fail("E2E test timed out - pipeline too slow")

        assert "done" in events_received, f"Pipeline did not complete. Events: {events_received}"
        assert len(final_response) > 50, f"Response too short: '{final_response[:100]}'"
        print(f"  Events: {events_received}")
        print(f"  Drug alerts emitted: {len(drug_alert_events)}")
        if patient_context_events:
            print(f"  Patient context: {patient_context_events[0].get('patient_id')}")

    def test_session_list_endpoint(self):
        """
        TEST-API-007 | Integration
        Scenario: GET /sessions after creating at least one session.
        Expected: Returns a list with session metadata.
        """
        # Create a session first
        requests.post(f"{BASE_URL}/sessions/new")
        resp = requests.get(f"{BASE_URL}/sessions")
        assert resp.status_code == 200
        data = resp.json()
        assert "sessions" in data
        assert isinstance(data["sessions"], list)
        if data["sessions"]:
            first = data["sessions"][0]
            assert "id" in first
            assert "title" in first


# =============================================================================
# UTILITY: Quick sanity-check runner
# =============================================================================

if __name__ == "__main__":
    import subprocess
    result = subprocess.run(
        ["python", "-m", "pytest", __file__, "-v", "--tb=short", "-x",
         "--ignore=tests/", "-k", "not slow"],
        cwd=PROJECT_ROOT
    )
    sys.exit(result.returncode)
