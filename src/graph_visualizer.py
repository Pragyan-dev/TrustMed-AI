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


# =============================================================================
# Graph Data Fetcher
# =============================================================================

class GraphVisualizer:
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))

    def close(self):
        self.driver.close()

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

        with self.driver.session(database="neo4j") as session:
            result = session.run(query, term=search_term).single()

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
