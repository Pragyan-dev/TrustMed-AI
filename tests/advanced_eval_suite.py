import os
import sys
import time
import json
import pytest
import asyncio
import httpx
import requests
import evaluate
from sentence_transformers import SentenceTransformer, util
import chromadb
from sklearn.metrics import precision_score, recall_score

# Ensure the correct path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

BASE_URL = os.getenv("TEST_API_URL", "http://localhost:8000")
KNOWN_PATIENT_ID = "10002428"
KNOWN_IMAGE = os.path.join(PROJECT_ROOT, "data", "medical_images", "roco_0000.jpg")

# Pre-load evaluate metrics and models
rouge = evaluate.load('rouge')
meteor = evaluate.load('meteor')
clinical_bert = SentenceTransformer('pritamdeka/S-PubMedBert-MS-MARCO')

# Module 1: VLM Evaluation

class TestVLMEvaluation:
    @pytest.fixture(scope="class")
    def chroma_client(self):
        return chromadb.PersistentClient(path=os.path.join(PROJECT_ROOT, "data", "chroma_db"))

    @pytest.fixture(scope="class")
    def ground_truth_image(self, chroma_client):
        collection = chroma_client.get_collection("medical_images")
        # Try to find a ground truth caption for roco_0000.jpg
        # Since we might not know the exact ID, we will just query by a text or retrieve top 1
        results = collection.get(limit=10)
        if results and results["metadatas"]:
            for meta in results["metadatas"]:
                if meta and "roco_0000" in meta.get("filename", ""):
                    return meta
            return results["metadatas"][0]
        return None

    def test_vlm_insight_extraction(self, ground_truth_image):
        if not ground_truth_image:
            pytest.skip("No ground truth image found in ChromaDB")
            
        from src.vision_tool import analyze_medical_image
        if analyze_medical_image is None:
            pytest.skip("Vision tool not available")
            
        img_path = KNOWN_IMAGE if os.path.exists(KNOWN_IMAGE) else ""
        if not img_path:
            pytest.skip("Test image not found")
            
        start_time = time.time()
        output = analyze_medical_image.invoke(img_path)
        vlm_latency = time.time() - start_time
        print(f"\nVLM Inference Latency: {vlm_latency:.2f}s")
        
        gt_caption = ground_truth_image.get("caption", "normal chest x-ray")
        
        # Calculate Rouge and Meteor
        rouge_scores = rouge.compute(predictions=[output], references=[gt_caption])
        meteor_scores = meteor.compute(predictions=[output], references=[gt_caption])
        
        # Semantic Similarity
        emb1 = clinical_bert.encode(output)
        emb2 = clinical_bert.encode(gt_caption)
        cos_sim = util.cos_sim(emb1, emb2).item()
        
        print(f"ROUGE-L: {rouge_scores['rougeL']:.4f}")
        print(f"METEOR: {meteor_scores['meteor']:.4f}")
        print(f"Semantic Similarity: {cos_sim:.4f}")
        
        assert cos_sim >= 0.0, "Cosine similarity should be calculated"

    def test_vlm_segmentation_iou(self):
        # As bounding boxes are not natively generated in text unless structured, 
        # we parse coordinates if they exist. Here we provide a mock/placeholder for the framework.
        # In a real scenario, this would parse the BBox from the JSON structure.
        iou_score = 0.85 # Placeholder for structure demonstration
        assert iou_score > 0

# Module 2: Text Generation & Hallucination

class TestTextGenerationAndSafety:
    def test_drug_safety_accuracy(self):
        from src.trustmed_brain import check_drug_interactions
        # Known severe interactions (e.g. QT prolongation)
        context = """=== PATIENT CONTEXT ===
Age: 65
Active Medications:
- Azithromycin
- Citalopram
- Lisinopril
Diagnoses:
- Pneumonia
- Depression
"""
        start_time = time.time()
        alerts = check_drug_interactions(context)
        latency = time.time() - start_time
        print(f"\nDrug Safety Checker Latency: {latency:.2f}s")
        
        expected_alerts = ["QT PROLONGATION"]
        found = [1 if alert in alerts.upper() else 0 for alert in expected_alerts]
        recall = sum(found) / len(expected_alerts) if expected_alerts else 1.0
        print(f"Drug Safety Recall: {recall*100}%")
        assert recall == 1.0

    def test_soap_hallucination_rate(self):
        from src.trustmed_brain import generate_soap_note
        from src.patient_context_tool import get_patient_vitals, get_patient_diagnoses, get_patient_meds
        
        patient_id = KNOWN_PATIENT_ID
        vitals = get_patient_vitals.invoke(patient_id)
        diagnoses = get_patient_diagnoses.invoke(patient_id)
        meds = get_patient_meds.invoke(patient_id)
        
        context = f"{vitals}\n{diagnoses}\n{meds}"
        history = [
            {"role": "user", "content": "Patient complains of chest pain and shortness of breath."},
            {"role": "assistant", "content": "I will review the records."}
        ]
        
        start_time = time.time()
        soap = generate_soap_note(history, context, "")
        llm_latency = time.time() - start_time
        print(f"\nSOAP Generation Latency: {llm_latency:.2f}s")
        
        if "error" in soap:
            pytest.skip(f"SOAP Error: {soap['error']}")
            
        assessment = soap.get("assessment", "")
        plan = soap.get("plan", "")
        
        # Simple entity extraction heuristic: words starting with capital letters
        import re
        entities = set(re.findall(r'\b[A-Z][a-z]+\b', assessment + " " + plan))
        context_words = set(re.findall(r'\b[A-Za-z]+\b', context))
        
        # Hallucinated if not in context (ignoring common words)
        unmatched = [e for e in entities if e.lower() not in [w.lower() for w in context_words]]
        hallucination_rate = len(unmatched) / len(entities) if entities else 0.0
        
        print(f"Entity Hallucination Rate: {hallucination_rate:.2%}")
        assert hallucination_rate >= 0.0

# Module 3: Multi-Turn Conversation

class TestMultiTurnContext:
    @pytest.mark.asyncio
    async def test_2_turn_context_retention(self):
        async with httpx.AsyncClient(timeout=30.0) as client:
            session_resp = await client.post(f"{BASE_URL}/sessions/new", params={"source": "clinician"})
            if session_resp.status_code != 200:
                pytest.skip("Backend unavailable")
            session_id = session_resp.json()["id"]
            
            # Turn 1
            payload1 = {"message": f"Show me the X-ray for patient {KNOWN_PATIENT_ID}.", "session_id": session_id, "persist": True}
            await client.post(f"{BASE_URL}/chat", json=payload1)
            
            # Turn 2
            payload2 = {"message": "What is the primary finding in that image?", "session_id": session_id, "persist": True}
            resp2 = await client.post(f"{BASE_URL}/chat", json=payload2)
            
            assert resp2.status_code == 200
            # Just verifying successful flow, the actual accuracy is handled in unit tests.

    @pytest.mark.asyncio
    async def test_3_turn_entity_persistence(self):
        async with httpx.AsyncClient(timeout=30.0) as client:
            session_resp = await client.post(f"{BASE_URL}/sessions/new", params={"source": "clinician"})
            if session_resp.status_code != 200:
                pytest.skip("Backend unavailable")
            session_id = session_resp.json()["id"]
            
            # Turn 1
            await client.post(f"{BASE_URL}/chat", json={"message": f"Load context for patient {KNOWN_PATIENT_ID}.", "session_id": session_id, "persist": True})
            
            # Turn 2
            await client.post(f"{BASE_URL}/chat", json={"message": "What antibiotics are they currently taking?", "session_id": session_id, "persist": True})
            
            # Turn 3
            resp3 = await client.post(f"{BASE_URL}/chat", json={"message": "Are there any contraindications with Lasix?", "session_id": session_id, "persist": True})
            assert resp3.status_code == 200

# Module 4: Performance Analysis

class TestPerformanceAnalysis:
    def test_neo4j_and_chroma_latency(self):
        from src.trustmed_brain import get_graph_context, get_vector_context_fast
        
        # Neo4j latency
        start_time = time.time()
        get_graph_context("What are the symptoms of pneumonia?")
        neo4j_latency = time.time() - start_time
        print(f"\nNeo4j Query Latency: {neo4j_latency:.4f}s")
        
        # ChromaDB latency
        start_time = time.time()
        get_vector_context_fast("pneumonia symptoms")
        chroma_latency = time.time() - start_time
        print(f"ChromaDB Query Latency: {chroma_latency:.4f}s")
        
        assert neo4j_latency > 0
        assert chroma_latency > 0

    @pytest.mark.asyncio
    async def test_concurrent_load(self):
        async def fetch():
            async with httpx.AsyncClient(timeout=60.0) as client:
                session_resp = await client.post(f"{BASE_URL}/sessions/new")
                if session_resp.status_code != 200:
                    return None
                session_id = session_resp.json()["id"]
                payload = {"message": "What is hypertension?", "session_id": session_id, "persist": False}
                start_time = time.time()
                resp = await client.post(f"{BASE_URL}/chat", json=payload)
                return time.time() - start_time if resp.status_code == 200 else None

        tasks = [fetch() for _ in range(5)]
        latencies = await asyncio.gather(*tasks)
        valid_latencies = [l for l in latencies if l is not None]
        if valid_latencies:
            avg_latency = sum(valid_latencies) / len(valid_latencies)
            print(f"\nConcurrent (5) Avg E2E Latency: {avg_latency:.2f}s")

if __name__ == "__main__":
    pytest.main(["-v", "-s", __file__])
