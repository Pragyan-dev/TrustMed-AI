
import os
import sqlite3

PROJECT_ROOT = "/Users/mansinandkar/Documents/SYNAPSE_GIT/TrustMed-AI"
DB_PATH = os.path.join(PROJECT_ROOT, "data", "mimic_demo.db")

def query_db(query, params=()):
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        return results
    except Exception as e:
        print(f"[DB Error] {e}")
        return []

def test(patient_id):
    print(f"Testing patient_id: {patient_id} (type: {type(patient_id)})")
    
    # Check vitals
    v_rows = query_db("SELECT count(*) as c FROM vitalsign WHERE subject_id = ?", (patient_id,))
    print(f"Vitals count: {v_rows[0]['c']}")
    
    # Check diagnoses
    d_rows = query_db("SELECT count(*) as c FROM diagnosis WHERE subject_id = ?", (patient_id,))
    print(f"Diagnoses count: {d_rows[0]['c']}")
    
    # Check medrecon
    m_rows = query_db("SELECT count(*) as c FROM medrecon WHERE subject_id = ?", (patient_id,))
    print(f"Medications count: {m_rows[0]['c']}")

if __name__ == "__main__":
    test("10027602")
    test(10027602)
