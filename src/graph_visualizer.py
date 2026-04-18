"""
Graph Visualizer Module

Fetches graph data from Neo4j and formats it as plain JSON
for the React frontend (react-force-graph-2d).
Includes Disease, Symptom, Precaution, Drug, and Condition nodes
with all relationship types.
"""

import os
from dotenv import load_dotenv
from neo4j import GraphDatabase
from src.ssl_bootstrap import configure_ssl_certificates

load_dotenv()
configure_ssl_certificates()

# =============================================================================
# Configuration
# =============================================================================

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

# Node colors by type
COLORS = {
    "Disease":    "#FF4B4B",   # Red
    "Symptom":    "#FFA500",   # Orange
    "Precaution": "#636EFA",   # Blue
    "Drug":       "#00CC96",   # Green
    "Condition":  "#E879F9",   # Purple
    "Patient":    "#555555",   # Gray
}

SIZES = {
    "Disease":    45,
    "Drug":       28,
    "Symptom":    20,
    "Precaution": 18,
    "Condition":  22,
    "Patient":    30,
}

# ── Alias map: MIMIC-IV / ICD diagnosis names → Kaggle KG disease names ──
# The Neo4j graph contains ~41 diseases from the Kaggle dataset.  The frontend
# frequently searches with MIMIC-IV ICD titles (e.g. "INTRACEREBRAL HEMORRHAGE")
# or clinical shorthand that doesn't match any Kaggle name.  This map bridges
# the vocabulary gap so that the graph panel shows relevant results.
#
# Keys are lowercased MIMIC / clinical terms (substrings are fine).
# Values are the exact Kaggle disease name stored in Neo4j.
_DIAGNOSIS_ALIASES = {
    # Cardiovascular / cerebrovascular
    "intracerebral hemorrhage":         "Paralysis (brain hemorrhage)",
    "brain hemorrhage":                 "Paralysis (brain hemorrhage)",
    "cerebral hemorrhage":              "Paralysis (brain hemorrhage)",
    "hemorrhagic stroke":               "Paralysis (brain hemorrhage)",
    "subarachnoid hemorrhage":          "Paralysis (brain hemorrhage)",
    "subdural hemorrhage":              "Paralysis (brain hemorrhage)",
    "subdural hematoma":                "Paralysis (brain hemorrhage)",
    "traumatic subdural":               "Paralysis (brain hemorrhage)",
    "myocardial infarction":            "Heart attack",
    "nstemi":                           "Heart attack",
    "stemi":                            "Heart attack",
    "non-st elevation":                 "Heart attack",
    "non-st elevation mi":              "Heart attack",
    "non-st elevation myocardial infarction": "Heart attack",
    "st elevation":                     "Heart attack",
    "st elevation myocardial infarction": "Heart attack",
    "mi":                               "Heart attack",
    "acute coronary syndrome":          "Heart attack",
    "heart failure":                    "Heart attack",
    "congestive heart failure":         "Heart attack",
    "cardiac arrest":                   "Heart attack",
    "atrial fibrillation":              "Heart attack",
    "atrial flutter":                   "Heart attack",
    "hypertension nos":                 "Hypertension",
    "essential hypertension":           "Hypertension",
    "hypertensive":                     "Hypertension",

    # Respiratory
    "pneumonia":                        "Pneumonia",
    "lobar pneumonia":                  "Pneumonia",
    "respiratory failure":              "Pneumonia",
    "respiratory arrest":               "Pneumonia",
    "acute respiratory failure":        "Pneumonia",
    "lung edema":                       "Pneumonia",
    "pleural effusion":                 "Pneumonia",
    "pneumothorax":                     "Pneumonia",
    "bronchial asthma":                 "Bronchial Asthma",
    "asthma":                           "Bronchial Asthma",
    "acute uri":                        "Common Cold",
    "common cold":                      "Common Cold",
    "cough":                            "Common Cold",
    "acute laryngitis":                 "Common Cold",
    "tuberculosis":                     "Tuberculosis",

    # GI / hepatic
    "gastrointestinal hemorrhage":      "Peptic ulcer diseae",
    "gastrointestinal hemorr":          "Peptic ulcer diseae",
    "hematemesis":                      "Peptic ulcer diseae",
    "rectal hemorrhage":                "Dimorphic hemmorhoids(piles)",
    "anal hemorrhage":                  "Dimorphic hemmorhoids(piles)",
    "hemorrhoids":                      "Dimorphic hemmorhoids(piles)",
    "gastroenteritis":                  "Gastroenteritis",
    "noninf gastroenterit":             "Gastroenteritis",
    "diarrhea":                         "Gastroenteritis",
    "cirrhosis":                        "Alcoholic hepatitis",
    "alcoholic hepatitis":              "Alcoholic hepatitis",
    "hepatitis a":                      "hepatitis A",
    "hepatitis b":                      "Hepatitis B",
    "hepatitis c":                      "Hepatitis C",
    "hepatitis d":                      "Hepatitis D",
    "hepatitis e":                      "Hepatitis E",
    "viral hepatitis":                  "Hepatitis B",
    "jaundice":                         "Jaundice",
    "cholestasis":                      "Chronic cholestasis",
    "gerd":                             "GERD",
    "peptic ulcer":                     "Peptic ulcer diseae",
    "intestinal obstruction":           "Peptic ulcer diseae",
    "acute appendicitis":               "Peptic ulcer diseae",
    "acute pancreatitis":               "Peptic ulcer diseae",

    # Endocrine / metabolic
    "diabetes":                         "Diabetes",
    "diabetic":                         "Diabetes",
    "diab ketoacidosis":                "Diabetes",
    "type 1 diabetes":                  "Diabetes",
    "type 2 diabetes":                  "Diabetes",
    "hypoglycemia":                     "Hypoglycemia",
    "hypothyroidism":                   "Hypothyroidism",
    "hyperthyroidism":                  "Hyperthyroidism",
    "hypercholesterolemia":             "Heart attack",
    "hyperlipidemia":                   "Heart attack",

    # Neurological
    "grand mal":                        "Paralysis (brain hemorrhage)",
    "convulsions":                      "Paralysis (brain hemorrhage)",
    "seizure":                          "Paralysis (brain hemorrhage)",
    "cerebral infarction":              "Paralysis (brain hemorrhage)",
    "encephalopathy":                   "Paralysis (brain hemorrhage)",
    "alzheimer":                        "Paralysis (brain hemorrhage)",
    "dementia":                         "Paralysis (brain hemorrhage)",
    "migraine":                         "Migraine",
    "headache":                         "Migraine",
    "vertigo":                          "(vertigo) Paroymsal  Positional Vertigo",
    "dizziness":                        "(vertigo) Paroymsal  Positional Vertigo",

    # Musculoskeletal
    "cervical spondylosis":             "Cervical spondylosis",
    "cervicalgia":                      "Cervical spondylosis",
    "lumbago":                          "Cervical spondylosis",
    "low back pain":                    "Cervical spondylosis",
    "dorsalgia":                        "Cervical spondylosis",
    "osteoarthritis":                   "Osteoarthristis",
    "arthritis":                        "Arthritis",
    "joint pain":                       "Arthritis",
    "varicose veins":                   "Varicose veins",

    # Infectious
    "sepsis":                           "Typhoid",
    "septicemia":                       "Typhoid",
    "septic shock":                     "Typhoid",
    "typhoid":                          "Typhoid",
    "malaria":                          "Malaria",
    "dengue":                           "Dengue",
    "chicken pox":                      "Chicken pox",
    "aids":                             "AIDS",
    "hiv":                              "AIDS",
    "impetigo":                         "Impetigo",
    "fungal infection":                 "Fungal infection",
    "cellulitis":                       "Impetigo",

    # Dermatological
    "psoriasis":                        "Psoriasis",
    "acne":                             "Acne",

    # Renal / urological
    "urinary tract infection":          "Urinary tract infection",
    "uti":                              "Urinary tract infection",
    "kidney disease":                   "Urinary tract infection",
    "kidney failure":                   "Urinary tract infection",
    "renal":                            "Urinary tract infection",

    # Allergy / drug reaction
    "allergy":                          "Allergy",
    "drug reaction":                    "Drug Reaction",
    "adverse effect":                   "Drug Reaction",

    # Fractures → mapped to nearest relevant disease for context
    "fracture of femur":                "Osteoarthristis",
    "fracture":                         "Osteoarthristis",
}


def _resolve_search_term(search_term: str) -> str:
    """
    Resolve a clinical / MIMIC-IV diagnosis name to a Kaggle KG disease name.

    Strategy:
      1. Direct alias lookup (case-insensitive substring match against alias keys)
      2. Individual keyword fallback — split into words and check each
      3. Return the original term if nothing matched (the Cypher CONTAINS
         will handle partial matches in Neo4j itself)
    """
    lower = search_term.strip().lower()

    # 1. Check if any alias key is a substring of the search term (or vice versa)
    for alias_key, kg_name in _DIAGNOSIS_ALIASES.items():
        if alias_key in lower or lower in alias_key:
            return kg_name

    # 2. Keyword fallback: try each significant word individually
    words = [w for w in lower.split() if len(w) > 3]
    for word in words:
        for alias_key, kg_name in _DIAGNOSIS_ALIASES.items():
            if word in alias_key:
                return kg_name

    return search_term


# =============================================================================
# Graph Data Fetcher
# =============================================================================

class GraphVisualizer:
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    def close(self):
        self.driver.close()

    def _all_disease_names(self, session) -> list:
        if not hasattr(self, "_disease_name_cache"):
            rows = session.run("MATCH (d:Disease) RETURN d.name AS name").data()
            self._disease_name_cache = [r["name"] for r in rows if r.get("name")]
            print(f"📚 Cached {len(self._disease_name_cache)} Disease names from Neo4j")
        return self._disease_name_cache

    def get_graph_json(self, search_term: str, patient_id: str = None) -> dict:
        """
        Fetch subgraph for a search term and return plain JSON dict.
        Returns { nodes: [...], edges: [...], stats: {...} }
        """
        if not search_term or len(search_term.strip()) < 2:
            return {"nodes": [], "edges": [], "stats": {}}

        print(f"🔎 Graph Search: '{search_term}' (Patient: {patient_id})")

        nodes = {}   # id -> node dict
        edges = []   # list of edge dicts

        # ── Main query: Disease + Symptoms + Precautions + Drugs + Contraindications ──
        query = """
        MATCH (d:Disease)
        WHERE toLower(d.name) CONTAINS toLower($term)
        
        OPTIONAL MATCH (d)-[:HAS_SYMPTOM]->(s:Symptom)
        OPTIONAL MATCH (d)-[:HAS_PRECAUTION]->(p:Precaution)
        OPTIONAL MATCH (drug:Drug)-[t:TREATS]->(d)
        OPTIONAL MATCH (drug2:Drug)-[ci:CONTRAINDICATED_WITH]->(d)
        
        RETURN d.name as disease,
               d.description as description,
               d.cui as cui,
               collect(DISTINCT {name: s.name, severity: s.severity, cui: s.cui}) as symptoms,
               collect(DISTINCT p.name) as precautions,
               collect(DISTINCT {name: drug.name, class: drug.drug_class, dosage: drug.common_dosage, line: t.line}) as drugs,
               collect(DISTINCT {name: drug2.name, severity: ci.severity, reason: ci.reason}) as contraindications
        LIMIT 1
        """

        with self.driver.session() as session:
            db_names = self._all_disease_names(session)
            db_names_lower = {n.lower(): n for n in db_names}
            s_low = search_term.strip().lower()

            candidates = []

            # Strategy 1: exact (case-insensitive) match against DB names
            if s_low in db_names_lower:
                candidates.append(db_names_lower[s_low])

            # Strategy 2: alias resolution (run before loose DB substring match
            # so curated clinical aliases beat coincidental letter overlaps)
            resolved = _resolve_search_term(search_term)
            if resolved and resolved.lower() in db_names_lower:
                canonical = db_names_lower[resolved.lower()]
                if canonical not in candidates:
                    candidates.append(canonical)

            # Strategy 3: substring match in either direction against DB names
            for low, original in db_names_lower.items():
                if low in s_low or s_low in low:
                    if original not in candidates:
                        candidates.append(original)

            # Strategy 4: token fallback — match each significant word against DB names
            if not candidates:
                for word in [w for w in s_low.split() if len(w) > 3]:
                    for low, original in db_names_lower.items():
                        if word in low and original not in candidates:
                            candidates.append(original)

            print(f"🔎 Graph Search: '{search_term}' → candidates={candidates[:3]}")

            if not candidates:
                print(f"   ⚠ No DB match. Available names sample: {db_names[:5]}")
                return {"nodes": [], "edges": [], "stats": {}}

            result = session.run(query, term=candidates[0]).single()
            if not result:
                return {"nodes": [], "edges": [], "stats": {}}

            disease_name = result["disease"]
            disease_desc = result["description"] or ""
            disease_cui = result["cui"] or ""
            symptoms = [s for s in result["symptoms"] if s["name"]]
            precautions = [p for p in result["precautions"] if p]
            drugs = [d for d in result["drugs"] if d["name"]]
            contraindications = [c for c in result["contraindications"] if c["name"]]

            # ── Disease node ──
            disease_id = f"Disease_{disease_name}"
            nodes[disease_id] = {
                "id": disease_id,
                "label": disease_name,
                "type": "Disease",
                "color": COLORS["Disease"],
                "size": SIZES["Disease"],
                "title": disease_desc,
                "cui": disease_cui,
            }

            # ── Symptom nodes ──
            for s in symptoms:
                sid = f"Symptom_{s['name']}"
                if sid not in nodes:
                    nodes[sid] = {
                        "id": sid,
                        "label": s["name"],
                        "type": "Symptom",
                        "color": COLORS["Symptom"],
                        "size": SIZES["Symptom"],
                        "title": f"Severity: {s['severity']}" if s.get("severity") else "",
                        "severity": s.get("severity"),
                    }
                    edges.append({
                        "source": disease_id,
                        "target": sid,
                        "label": "HAS_SYMPTOM",
                        "color": COLORS["Symptom"],
                        "width": 1.5,
                        "dashes": False,
                    })

            # ── Precaution nodes ──
            for p in precautions:
                pid = f"Precaution_{p}"
                if pid not in nodes:
                    nodes[pid] = {
                        "id": pid,
                        "label": p,
                        "type": "Precaution",
                        "color": COLORS["Precaution"],
                        "size": SIZES["Precaution"],
                        "title": "",
                    }
                    edges.append({
                        "source": disease_id,
                        "target": pid,
                        "label": "HAS_PRECAUTION",
                        "color": COLORS["Precaution"],
                        "width": 1,
                        "dashes": True,
                    })

            # ── Drug nodes (TREATS) ──
            for d in drugs:
                did = f"Drug_{d['name']}"
                if did not in nodes:
                    nodes[did] = {
                        "id": did,
                        "label": d["name"],
                        "type": "Drug",
                        "color": COLORS["Drug"],
                        "size": SIZES["Drug"],
                        "title": f"{d.get('class', '')} — {d.get('dosage', '')}",
                        "drug_class": d.get("class", ""),
                        "dosage": d.get("dosage", ""),
                        "line": d.get("line", ""),
                    }
                line_label = "1st line" if d.get("line") == "first_line" else "2nd line"
                edges.append({
                    "source": did,
                    "target": disease_id,
                    "label": f"TREATS ({line_label})",
                    "color": COLORS["Drug"],
                    "width": 2,
                    "dashes": False,
                })

            # ── Contraindication edges ──
            for c in contraindications:
                cid = f"Drug_{c['name']}"
                # Only add if the drug node exists (avoids duplicates with TREATS drugs)
                if cid not in nodes:
                    nodes[cid] = {
                        "id": cid,
                        "label": c["name"],
                        "type": "Drug",
                        "color": COLORS["Drug"],
                        "size": SIZES["Drug"],
                        "title": f"⚠️ {c.get('reason', '')}",
                    }
                edges.append({
                    "source": cid,
                    "target": disease_id,
                    "label": "CONTRAINDICATED",
                    "color": "#EF4444",
                    "width": 2,
                    "dashes": True,
                })

            # ── Drug-Drug Interactions for drugs that treat this disease ──
            drug_names = [d["name"] for d in drugs]
            if len(drug_names) >= 2:
                ix_result = session.run("""
                    MATCH (d1:Drug)-[r:INTERACTS_WITH]-(d2:Drug)
                    WHERE d1.name IN $names AND d2.name IN $names
                      AND elementId(d1) < elementId(d2)
                    RETURN d1.name as drug1, d2.name as drug2,
                           r.severity as severity, r.effect as effect
                """, names=drug_names)

                for ix in ix_result:
                    edges.append({
                        "source": f"Drug_{ix['drug1']}",
                        "target": f"Drug_{ix['drug2']}",
                        "label": f"INTERACTS ({ix['severity']})",
                        "color": "#EF4444" if ix["severity"] == "major" else "#F59E0B",
                        "width": 2.5,
                        "dashes": True,
                    })

            # ── Patient node (if provided) ──
            if patient_id:
                pid = f"Patient_{patient_id}"
                nodes[pid] = {
                    "id": pid,
                    "label": f"Patient {patient_id}",
                    "type": "Patient",
                    "color": COLORS["Patient"],
                    "size": SIZES["Patient"],
                    "title": f"Patient ID: {patient_id}",
                }
                edges.append({
                    "source": pid,
                    "target": disease_id,
                    "label": "DIAGNOSIS",
                    "color": COLORS["Patient"],
                    "width": 2,
                    "dashes": False,
                })

        # Build stats
        stats = {
            "symptoms": len([n for n in nodes.values() if n["type"] == "Symptom"]),
            "precautions": len([n for n in nodes.values() if n["type"] == "Precaution"]),
            "drugs": len([n for n in nodes.values() if n["type"] == "Drug"]),
            "interactions": len([e for e in edges if "INTERACTS" in e.get("label", "")]),
            "contraindications": len([e for e in edges if "CONTRAINDICATED" in e.get("label", "")]),
        }

        print(f"  ✓ Graph: {len(nodes)} nodes, {len(edges)} edges "
              f"({stats['drugs']} drugs, {stats['symptoms']} symptoms, "
              f"{stats['precautions']} precautions)")

        return {
            "nodes": list(nodes.values()),
            "edges": edges,
            "stats": stats,
        }


# Helper function
def get_graph_json(search_term: str, patient_id: str = None) -> dict:
    viz = GraphVisualizer()
    data = viz.get_graph_json(search_term, patient_id)
    viz.close()
    return data
