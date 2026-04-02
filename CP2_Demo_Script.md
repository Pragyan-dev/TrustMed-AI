# Synapse AI - Checkpoint 2 Frontend Demo Script

**Duration:** ~8-10 minutes
**Presenters:** Team Alabama

---

## Opening (30 seconds)

> "This is Synapse AI, our neuro-symbolic clinical decision support system. It combines a knowledge graph, vector retrieval, medical vision analysis, and drug safety checking into a unified interface. Today we'll walk through both the clinician and patient-facing experiences."

---

## 1. Role Selector (30 seconds)

**Navigate to:** `localhost:5173`

> "Our landing page gives two entry points, the Clinician Dashboard for healthcare providers and the Patient Portal for patients to understand their own records. Let's start with the clinician view."

**Click:** Clinician Dashboard

---

## 2. Clinician Dashboard - Setup (1 minute)

**Show:** Empty state with readiness cards and system status

> "The clinician dashboard shows system readiness at a glance. On the left you can see our four backend engines: Knowledge Graph powered by Neo4j, Vector Store using ChromaDB, the MIMIC-IV clinical database, and our Drug Safety Engine. All four are operational."

**Click:** Settings drawer

> "Clinicians can select from multiple text synthesis models. We have MedGemma 27B running on Vertex AI as our flagship medical model, plus five OpenRouter alternatives for different use cases. There's also a separate vision model selector and a temperature control for generation."

**Select:** Patient 10002428 from the left sidebar

> "When a patient is selected, their vitals and conditions load inline so the clinician always has context while chatting."

---

## 3. Clinician Dashboard - Multimodal Chat (2 minutes)

**Type a clinical question:** "What are the key concerns for this patient based on their vitals and conditions?"

> "The system streams its response in real time through our SSE pipeline. Watch the status badges at the top — they light up as each subsystem activates: knowledge graph retrieval, vector search, drug safety check, and the safety critic layer."

**Wait for response to stream**

> "The response synthesizes data from multiple sources — the patient's MIMIC-IV record, the knowledge graph for clinical relationships, and the drug safety engine for medication interactions."

**Show Drug Safety tab on right panel:**

> "The Drug Safety panel shows alerts from our deterministic Neo4j graph traversal. This isn't LLM-generated — it's rule-based checking for drug interactions, contraindications, QT prolongation risk, bleeding risk, duplicate therapy, and Beers criteria for elderly patients."

---

## 4. Medical Image Analysis (1.5 minutes)

**Drag a chest X-ray into the imaging panel (or paste from clipboard)**

> "Clinicians can upload medical images by drag-and-drop or paste from clipboard. Let me upload a chest X-ray."

**Type:** "Analyze this chest X-ray and identify any abnormalities"

> "The vision pipeline sends the image to our MedGemma model on Vertex AI for analysis. It identifies findings like cardiomegaly, pleural effusions, or consolidation, then cross-references against the patient's known conditions from the knowledge graph."

**Show the Knowledge Graph tab:**

> "The knowledge graph panel visualizes the relationships between the patient's conditions, medications, and findings. This is powered by our Neo4j database with MIMIC-IV data."

---

## 5. SOAP Note Generation (1 minute)

**Click:** Notes tab on right panel
**Click:** Generate SOAP Note button

> "One of our key deliverables was automated SOAP note generation. The system pulls the patient's context, vitals history, and conversation findings to generate a structured Subjective, Objective, Assessment, and Plan note."

**Wait for SOAP note to generate**

> "This saves clinicians significant documentation time. The note is generated using the Nemotron 30B model to avoid rate limiting on our primary models."

---

## 6. Switch to Patient Portal (30 seconds)

**Click:** Switch Role in the top bar
**Click:** Patient Portal

> "Now let's see the same data from the patient's perspective. The patient portal presents clinical information in plain, non-technical language."

---

## 7. Patient Portal - Health Profile (1 minute)

**Select:** Patient 10002428

> "The portal opens with a personalized health summary. The hero section shows key metrics — active conditions, medication count, and last update. Below that, a plain-English summary explains the patient's current health status."

**Show:** Health Profile tab with conditions

> "Active conditions are mapped to friendly names. Instead of 'pneumonia,' patients see 'Lung Infection' with a severity badge and a simple explanation. This uses our condition mapping layer."

---

## 8. Patient Portal - Vitals (1.5 minutes)

**Click:** Vitals tab

> "The vitals section starts with summary cards — quick-glance tiles for each vital sign with sparkline trends and color-coded status badges. Green means in range, amber means watch, red means attention needed."

**Scroll to trend charts**

> "Below the summary cards are detailed trend charts with gradient area fills. The green band shows the normal range, dashed lines mark upper and lower thresholds, and each data point is interactive — hover to see exact values and timestamps. This represents the patient's last 16 bedside readings."

---

## 9. Patient Portal - Medications & Safety (1 minute)

**Click:** Medications tab

> "Medications are shown as cards with a Safety Check button on each one. Let me demonstrate the drug interaction checking."

**Click:** Safety Check on a medication

> "This triggers our drug safety pipeline against the patient's full medication list. The result comes back showing any interactions, contraindications, or dosing warnings — powered by the same Neo4j engine the clinician dashboard uses, but presented in patient-friendly language."

---

## 10. Patient Portal - Care Plan (30 seconds)

**Click:** Care Plan tab

> "The care plan section provides a personalized summary with vitals and medication explanations, followed by numbered next steps. This is generated from the patient's current chart data."

---

## 11. AI Assistant (30 seconds)

**Open the assistant panel (if minimized)**

> "Both views include an AI assistant. Patients can ask questions like 'What should I know about my medications?' and get answers grounded in their actual health record. Each section also has an 'Ask' button that pre-fills a contextual question."

---

## Closing (30 seconds)

> "To summarize what we've delivered for Checkpoint 2: MIMIC and Neo4j validation is complete, vision-text integration with MedGemma is working, SOAP note generation is deployed, and the drug safety pipeline is fully operational. Our remaining work focuses on safety critic refinement, performance testing, and final evaluation. Thank you."

---

## Demo Checklist

Before the demo, ensure:
- [ ] FastAPI backend running on port 8000
- [ ] Frontend dev server on port 5173
- [ ] Neo4j database accessible
- [ ] Have a chest X-ray image ready for upload
- [ ] Test with Patient 10002428 (has rich data)
- [ ] Check that MedGemma endpoint is warm (or use fallback model)
