# TrustMed AI 🏥🤖

**Neuro-Symbolic Clinical Decision Support System**

A multimodal medical AI assistant that combines patient records, knowledge graphs, medical literature, and medical imaging into one comprehensive clinical tool.

![System Architecture](system_architecture_clinical_assistant.png)

---

## 🎯 What It Does

TrustMed AI is designed to address three clinical pain points: **Time**, **Trust**, and **Liability**.

| Feature | Problem Solved | How |
|---------|---------------|-----|
| **4-Brain Architecture** | Fragmented information | Combines patient data, knowledge graphs, literature, and imaging |
| **Safety Critic Layer** | AI hallucinations | Every response reviewed for contraindications before display |
| **SOAP Note Generator** | Documentation burden | One-click clinical note generation |
| **Visual-RAG** | Missing historical context | Finds similar cases from image database |
| **Cross-Encoder Reranking** | Irrelevant search results | Deep semantic filtering (30 → 3 most relevant) |
| **Compound Figure Detection** | Multi-panel medical images | Auto-splits grids, analyzes each panel independently |

---

## 🧠 The Four Knowledge Sources

| Brain | Data Source | Example Output |
|-------|-------------|----------------|
| **Patient Context** | MIMIC-IV (SQLite) | "Patient 10002428: BP 145/92, on Lisinopril" |
| **Knowledge Graph** | Neo4j (AuraDB) | "Pneumonia → HAS_SYMPTOM → Cough, Fever" |
| **Medical Literature** | ChromaDB (Vector) | "WHO guidelines recommend..." |
| **Vision Agent** | BiomedCLIP + LLaMA 3.2 | "X-ray shows bilateral infiltrates, 92% similar to 5 pneumonia cases" |

---

## 🔄 Complete Pipeline (Query + Image)

```
User Input (Query + Image)
       ↓
┌─────────────────────────────────────┐
│ 🔲 COMPOUND FIGURE DETECTOR        │
│  • Detects multi-panel grids       │
│  • Splits into individual panels   │
│  • Labels: A, B, C, D...           │
└─────────────────────────────────────┘
       ↓ (for each panel)
┌─────────────────────────────────────┐
│ VISION AGENT (Multimodal)          │
│  • LLaMA 3.2 Vision → Findings     │
│  • Text-RAG → Guidelines           │
│  • Visual-RAG → Similar Cases      │
└─────────────────────────────────────┘
       ↓
┌─────────────────────────────────────┐
│ CROSS-PANEL SYNTHESIS              │
│  • Combines all panel analyses     │
│  • Generates unified report        │
└─────────────────────────────────────┘
       ↓
┌─────────────────────────────────────┐
│ PARALLEL RETRIEVAL                 │
│  • Patient Context (MIMIC)         │
│  • Knowledge Graph (Neo4j)         │
│  • Vector Search (ChromaDB)        │
└─────────────────────────────────────┘
       ↓
┌─────────────────────────────────────┐
│ RERANKER (Cross-Encoder)           │
│  • 30 candidates → Top 3 relevant  │
└─────────────────────────────────────┘
       ↓
┌─────────────────────────────────────┐
│ DRAFT GENERATION (LLM)             │
│  • Synthesizes all contexts        │
└─────────────────────────────────────┘
       ↓
┌─────────────────────────────────────┐
│ 🛡️ SAFETY CRITIC LAYER            │
│  • Checks contraindications        │
│  • Validates dosages               │
│  • Adds warnings if needed         │
└─────────────────────────────────────┘
       ↓
Final Response → User
```

---

## �️ Safety Features

### Self-Reflective Safety Layer
Every AI response passes through a second LLM review:
1. **Draft Generated** → Main LLM creates response
2. **Critic Reviews** → Safety agent checks for:
   - Dosage errors
   - Drug contraindications (vs patient meds)
   - Hallucinated treatments
3. **Safe Response** → Modified if needed, delivered to user

### SOAP Note Generator
One-click clinical documentation:
- **S**ubjective: Patient symptoms from chat
- **O**bjective: Vitals, imaging findings
- **A**ssessment: AI diagnosis/reasoning
- **P**lan: Recommendations

---

## � Compound Figure Detection

Medical publications often contain multi-panel images (e.g., 2×2 X-ray grids, pre/post comparisons). TrustMed AI automatically handles these:

### How It Works
1. **Detection**: OpenCV analyzes whitespace/borders to detect panel grids
2. **Splitting**: Each panel (A, B, C, D...) is cropped as a separate image
3. **Independent Analysis**: Full Vision+RAG pipeline runs on each panel
4. **Cross-Panel Synthesis**: AI generates a unified report comparing all panels

### Example
```
You: [Upload 2×2 chest X-ray grid] "Compare these scans"

UI: "Compound figure detected: 4 panels (2×2 grid)"

AI: "📋 Multi-Panel Analysis:

Panel A (Top-Left): Baseline chest X-ray, clear lung fields
Panel B (Top-Right): Day 3 - Early infiltrates in RLL
Panel C (Bottom-Left): Day 7 - Progressive consolidation
Panel D (Bottom-Right): Day 14 post-treatment - Resolving

🔗 Cross-Panel Synthesis:
This series shows progression and resolution of right lower
lobe pneumonia over 14 days with appropriate treatment response."
```

### During Ingestion
When batch-ingesting images, compound figures are automatically split and each subfigure is stored with:
- Its own BiomedCLIP embedding for Visual-RAG
- Parent-child metadata linking back to the original image

---

## �🖼️ Visual-RAG: Finding Similar Cases

When you upload a medical scan:

1. **BiomedCLIP** embeds the image into a vector
2. **ChromaDB** searches 1,800+ labeled medical images
3. **Returns**: Top 5 similar cases with diagnoses
4. **Example**: "This X-ray is 92% similar to 3 confirmed pneumonia cases"

---

## 📊 Tech Stack

| Component | Technology | Purpose |
|-----------|------------|---------|
| Frontend | Streamlit | Interactive clinical UI |
| Orchestrator | Python (LangChain) | Combines all knowledge sources |
| Knowledge Graph | Neo4j AuraDB | Disease-symptom-treatment relationships |
| Vector DB | ChromaDB | Text & image semantic search |
| Embeddings | Sentence Transformers | Text embeddings (all-MiniLM-L6-v2) |
| Medical Image AI | BiomedCLIP | Medical image embeddings |
| Vision Model | LLaMA 3.2 Vision / Gemini | Image analysis |
| Subfigure Detection | OpenCV + PIL | Compound figure grid detection |
| LLM | OpenRouter (Nemotron) | Response generation |
| Reranker | Cross-Encoder (ms-marco) | Deep relevance scoring |
| Patient Data | MIMIC-IV (SQLite) | Real ICU records (anonymized) |

---

## 🚀 Quick Start

### 1. Install Dependencies
```bash
pip install -r requirements.txt
```

### 2. Configure Environment
```bash
cp .env.example .env
# Add your API keys: OPENROUTER_API_KEY, NEO4J_URI, etc.
```

### 3. Run the App
```bash
python3 -m streamlit run app.py
```

### 4. Try These Queries
- **Patient Assessment**: "Assess patient 10002428 for any risks"
- **Drug Interaction**: "What are interactions between Lisinopril and Ibuprofen?"
- **Image Analysis**: Upload X-ray + "What does this scan show?"
- **Generate Notes**: Click "📄 Generate Clinical Note (SOAP)" after a conversation

---

## 📁 Project Structure

```
TrustMed-AI/
├── app.py                      # Streamlit frontend
├── src/
│   ├── trustmed_brain.py       # Main orchestrator (4 brains + safety)
│   ├── vision_agent.py         # Vision + Text-RAG + Visual-RAG + Compound support
│   ├── vision_tool.py          # LLaMA/Gemini vision model
│   ├── subfigure_detector.py   # OpenCV compound figure detection
│   ├── patient_context_tool.py # MIMIC-IV patient data
│   ├── reranker.py             # Cross-encoder reranking
│   └── graph_visualizer.py     # Neo4j → Streamlit-agraph
├── ingestion/
│   ├── ingest_diseases.py      # Disease/symptom data → Neo4j
│   ├── ingest_images.py        # Medical images → ChromaDB
│   └── ingest_xrays.py         # Labeled X-rays → ChromaDB
├── data/
│   ├── chroma_db/              # Vector store
│   └── mimic_iv.db             # Patient SQLite database
└── docs/
    ├── README.md               # This file
    └── system_architecture_*.png
```

---

## ✅ Completed Features

- [x] **Neuro-Symbolic Architecture** - Graph + Vector + Patient context fusion
- [x] **Advanced RAG** - Cross-encoder reranking for better retrieval
- [x] **Multimodal Vision Agent** - Vision + Text-RAG + Visual-RAG pipeline
- [x] **Knowledge Graph Visualization** - Interactive Neo4j graph in UI
- [x] **Self-Reflective Safety Layer** - Critic agent for contraindication checking
- [x] **SOAP Note Generator** - Automated clinical documentation
- [x] **BiomedCLIP Integration** - Medical image embeddings + similarity search
- [x] **Labeled X-ray Dataset** - 1,800 images with PNEUMONIA/NORMAL labels
- [x] **Compound Figure Detection** - Auto-split multi-panel images with cross-panel synthesis

---

## 🔮 Future Roadmap

- [ ] **DICOM Support** - Direct hospital image format ingestion
- [ ] **Uncertainty Quantification** - "80% confident this is pneumonia"
- [ ] **Drug Interaction API** - Real-time DrugBank/RxNorm integration
- [ ] **Voice Interface** - Speech-to-text for hands-free queries
- [ ] **Federated Learning** - Privacy-preserving model updates
- [ ] **FHIR Integration** - Connect to real EHR systems

---

## 📚 Data Sources

| Dataset | Size | Use |
|---------|------|-----|
| MIMIC-IV | 40K+ patients | Patient vitals, diagnoses, medications |
| ROCO | 2,000 images | Medical image similarity search |
| Kaggle Pneumonia | 1,800 images | Labeled X-ray training data |
| Disease-Symptom DB | 400+ diseases | Knowledge graph construction |

---

## 🎬 Demo Examples

### Patient Assessment
```
You: "Assess patient 10002428 for medication risks"

AI: "Patient 10002428 (65yo):
- BP: 145/92 (elevated)
- Current: Lisinopril 10mg, Metformin 500mg
- Diagnosis: Hypertension, Type 2 Diabetes

⚠️ Note: BP above target. Consider dose adjustment.
No drug interactions detected between current medications."
```

### Image Analysis with Similar Cases
```
You: [Upload chest X-ray] "Analyze this scan"

AI: "📋 Imaging Analysis:
Bilateral infiltrates visible in lower lobes.

🖼️ Similar Cases (Top 3):
1. Bacterial pneumonia (92% match)
2. Viral pneumonia (87% match)  
3. Aspiration pneumonia (81% match)

📖 Guidelines: CDC recommends empiric antibiotic 
therapy pending culture results..."
```

---

## 👤 Author

**Pragyan Borthakur**  
ASU Capstone Project - Spring 2026

---
