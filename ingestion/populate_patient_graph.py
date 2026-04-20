import os
import sqlite3
import sys
from neo4j import GraphDatabase
from dotenv import load_dotenv
from typing import List, Dict, Any

# Force UTF-8 encoding for Windows terminals
if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if sys.stderr and hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Add src to path for imports if needed
import sys
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
sys.path.insert(0, PROJECT_ROOT)

from src.umls_client import UMLSClient

load_dotenv(os.path.join(PROJECT_ROOT, '.env'))

# ----------------------------
# CONFIG
# ----------------------------
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'mimic_demo.db')
NEO4J_URI = os.environ.get("NEO4J_URI")
NEO4J_USER = os.environ.get("NEO4J_USERNAME")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD")
UMLS_API_KEY = os.environ.get("UMLS_API_KEY")

class PatientGraphPopulator:
    def __init__(self):
        self.driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
        self.umls = UMLSClient(api_key=UMLS_API_KEY)
        self.conn = sqlite3.connect(DB_PATH)
        self.conn.row_factory = sqlite3.Row

    def close(self):
        self.driver.close()
        self.conn.close()

    def get_patients(self) -> List[str]:
        cursor = self.conn.execute("SELECT DISTINCT subject_id FROM diagnosis")
        return [str(row['subject_id']) for row in cursor.fetchall()]

    def get_patient_diagnoses(self, subject_id: str) -> List[Dict[str, Any]]:
        cursor = self.conn.execute(
            "SELECT icd_code, icd_title FROM diagnosis WHERE subject_id = ?", 
            (subject_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_patient_vitals(self, subject_id: str) -> List[Dict[str, Any]]:
        cursor = self.conn.execute(
            "SELECT temperature, heartrate, resprate, o2sat, sbp, dbp, charttime FROM vitalsign WHERE subject_id = ? ORDER BY charttime DESC",
            (subject_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def get_patient_meds(self, subject_id: str) -> List[Dict[str, Any]]:
        cursor = self.conn.execute(
            "SELECT DISTINCT name, etcdescription FROM medrecon WHERE subject_id = ?",
            (subject_id,)
        )
        return [dict(row) for row in cursor.fetchall()]

    def populate(self):
        patients = self.get_patients()
        print(f"Found {len(patients)} patients in SQLite.")

        with self.driver.session() as session:
            for subject_id in patients:
                # Check for data presence
                diagnoses = self.get_patient_diagnoses(subject_id)
                vitals = self.get_patient_vitals(subject_id)
                meds = self.get_patient_meds(subject_id)
                
                if not diagnoses and not vitals and not meds:
                    print(f"Skipping Patient: {subject_id} (No data found)")
                    continue

                print(f"\nProcessing Patient: {subject_id}")
                
                # 1. Create/Update Patient Node
                session.run("""
                    MERGE (p:Patient {subject_id: $subject_id})
                    SET p.name = $name,
                        p.last_updated = timestamp()
                """, subject_id=subject_id, name=f"Patient {subject_id}")

                # 2. Process Diagnoses
                for diag in diagnoses:
                    term = diag['icd_title']
                    code = diag['icd_code']
                    
                    print(f"  Validating diagnosis: {term} ({code})...")
                    
                    # Try UMLS Linkage
                    result = self.umls.get_cui(term)
                    cui = None
                    umls_name = term
                    
                    if result:
                        cui, umls_name = result
                        print(f"    [OK] Linked to UMLS: {cui} ({umls_name})")
                    else:
                        print(f"    [MISSING] No UMLS linkage found for '{term}'")

                    # Create Disease Node & Link
                    session.run("""
                        MERGE (d:Disease {name: $name})
                        SET d.icd_code = $code,
                            d.cui = $cui,
                            d.last_updated = timestamp()
                        WITH d
                        MATCH (p:Patient {subject_id: $subject_id})
                        MERGE (p)-[:HAS_DIAGNOSIS]->(d)
                    """, name=umls_name, code=code, cui=cui, subject_id=subject_id)

                # 3. Process Vital Signs
                if vitals:
                    latest = vitals[0]
                    print(f"  Loading {len(vitals)} vitals (Latest: {latest['charttime']})...")
                    
                    # Clear existing historical vitals to avoid duplicates/orphans from previous runs
                    session.run("""
                        MATCH (p:Patient {subject_id: $subject_id})-[r:HAS_VITAL]->(v:VitalSign)
                        DELETE r, v
                    """, subject_id=subject_id)

                    # Store latest vitals directly on Patient for fast access
                    session.run("""
                        MATCH (p:Patient {subject_id: $subject_id})
                        SET p.temperature = $temp,
                            p.heart_rate = $hr,
                            p.respiratory_rate = $rr,
                            p.o2_saturation = $o2,
                            p.systolic_bp = $sbp,
                            p.diastolic_bp = $dbp,
                            p.vitals_last_updated = $time
                    """, 
                    subject_id=subject_id,
                    temp=latest['temperature'],
                    hr=latest['heartrate'],
                    rr=latest['resprate'],
                    o2=latest['o2sat'],
                    sbp=latest['sbp'],
                    dbp=latest['dbp'],
                    time=latest['charttime'])

                    # Create VitalSign nodes for historical tracking
                    for v_entry in vitals:
                        session.run("""
                            MATCH (p:Patient {subject_id: $subject_id})
                            MERGE (v:VitalSign {
                                subject_id: $subject_id,
                                timestamp: $time
                            })
                            SET v.temperature = $temp,
                                v.heart_rate = $hr,
                                v.respiratory_rate = $rr,
                                v.o2_saturation = $o2,
                                v.systolic_bp = $sbp,
                                v.diastolic_bp = $dbp
                            MERGE (p)-[:HAS_VITAL]->(v)
                        """,
                        subject_id=subject_id,
                        temp=v_entry['temperature'],
                        hr=v_entry['heartrate'],
                        rr=v_entry['resprate'],
                        o2=v_entry['o2sat'],
                        sbp=v_entry['sbp'],
                        dbp=v_entry['dbp'],
                        time=v_entry['charttime'])

                # 4. Process Medications
                meds = self.get_patient_meds(subject_id)
                for med in meds:
                    name = med['name']
                    desc = med['etcdescription']
                    if not name: continue

                    print(f"  Mapping medication: {name}...")
                    
                    # Try to get CUI for the drug
                    drug_result = self.umls.get_cui(name)
                    drug_cui = None
                    standard_name = name
                    if drug_result:
                        drug_cui, standard_name = drug_result
                    
                    # Link to Drug node (create if doesn't exist)
                    session.run("""
                        MERGE (d:Drug {name: $name})
                        SET d.cui = $cui,
                            d.last_updated = timestamp()
                        WITH d
                        MATCH (p:Patient {subject_id: $subject_id})
                        MERGE (p)-[r:TAKES_MEDICATION]->(d)
                        SET r.description = $desc,
                            r.last_updated = timestamp()
                    """, 
                    name=standard_name, 
                    cui=drug_cui, 
                    subject_id=subject_id,
                    desc=desc)

        print("\nKnowledge Graph population complete.")

if __name__ == "__main__":
    if not NEO4J_URI or not UMLS_API_KEY:
        print("Error: Missing NEO4J_URI or UMLS_API_KEY in environment.")
    else:
        populator = PatientGraphPopulator()
        try:
            populator.populate()
        finally:
            populator.close()
