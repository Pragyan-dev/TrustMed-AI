"""
Patient Context Tools for MIMIC Database

LangChain tools for retrieving patient vitals, diagnoses, and medications
from the SQLite MIMIC demo database.
"""

import os
import sqlite3
from langchain_core.tools import tool

# Configuration - use absolute path based on project root
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)  # Go up from src/ to project root
DB_PATH = os.path.join(_PROJECT_ROOT, 'data', 'mimic_demo.db')
VITAL_HISTORY_LIMIT = 16


def query_db(query, params=()):
    """
    Execute a SQL query safely and return results.
    
    Args:
        query: SQL query string with ? placeholders
        params: Tuple of parameters for the query
        
    Returns:
        List of sqlite3.Row objects, or empty list on error
    """
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row  # Access columns by name
        cursor = conn.cursor()
        cursor.execute(query, params)
        results = cursor.fetchall()
        conn.close()
        return results
    except Exception as e:
        print(f"[DB Error] {e}")
        return []


def _serialize_vitals_row(row):
    return {
        "temperature": row["temperature"],
        "heart_rate": row["heartrate"],
        "respiratory_rate": row["resprate"],
        "o2_saturation": row["o2sat"],
        "systolic_bp": row["sbp"],
        "diastolic_bp": row["dbp"],
        "recorded_at": row["charttime"],
    }


@tool
def get_patient_vitals(patient_id: str) -> str:
    """
    Get the most recent vital signs for a patient.
    
    Args:
        patient_id: The patient's subject_id from the database
        
    Returns:
        Formatted string with temperature, heart rate, respiratory rate,
        O2 saturation, and blood pressure, or 'No vitals found'.
    """
    query = """
        SELECT temperature, heartrate, resprate, o2sat, sbp, dbp, charttime 
        FROM vitalsign 
        WHERE subject_id = ? 
        ORDER BY charttime DESC 
        LIMIT 1
    """
    
    rows = query_db(query, (patient_id,))
    
    if not rows:
        return "No vitals found for this patient."
    
    row = rows[0]
    return (
        f"Latest Vitals (as of {row['charttime']}):\n"
        f"  • Temperature: {row['temperature']}°F\n"
        f"  • Heart Rate: {row['heartrate']} bpm\n"
        f"  • Respiratory Rate: {row['resprate']} breaths/min\n"
        f"  • O2 Saturation: {row['o2sat']}%\n"
        f"  • Blood Pressure: {row['sbp']}/{row['dbp']} mmHg"
    )


@tool
def get_patient_diagnoses(patient_id: str) -> str:
    """
    Get all diagnoses for a patient.
    
    Args:
        patient_id: The patient's subject_id from the database
        
    Returns:
        Formatted list of diagnoses with ICD codes, or 'No diagnoses found'.
    """
    query = """
        SELECT icd_title, icd_code 
        FROM diagnosis 
        WHERE subject_id = ?
    """
    
    rows = query_db(query, (patient_id,))
    
    if not rows:
        return "No diagnoses found for this patient."
    
    diagnoses = [f"- {row['icd_title']} (ICD: {row['icd_code']})" for row in rows]
    return "Diagnoses:\n" + "\n".join(diagnoses)


@tool
def get_patient_meds(patient_id: str) -> str:
    """
    Get active medications for a patient.
    
    Args:
        patient_id: The patient's subject_id from the database
        
    Returns:
        Unique list of medications with descriptions, or 'No medications found'.
    """
    query = """
        SELECT DISTINCT name, etcdescription 
        FROM medrecon 
        WHERE subject_id = ?
    """
    
    rows = query_db(query, (patient_id,))
    
    if not rows:
        return "No medications found for this patient."
    
    # Build unique list of medications
    seen = set()
    meds = []
    for row in rows:
        name = row['name']
        if name and name not in seen:
            seen.add(name)
            desc = row['etcdescription'] or ""
            meds.append(f"- {name}" + (f" ({desc})" if desc else ""))
    
    if not meds:
        return "No medications found for this patient."
    
    return "Active Medications:\n" + "\n".join(meds)

def get_patient_data_json(patient_id: str) -> dict:
    """
    Get structured patient data as a dict for the frontend API.
    Returns vitals, diagnoses, and medications as structured JSON.
    """
    result = {"patient_id": patient_id}

    # Vitals
    vitals_query = """
        SELECT temperature, heartrate, resprate, o2sat, sbp, dbp, charttime 
        FROM vitalsign 
        WHERE subject_id = ? 
        ORDER BY charttime DESC 
        LIMIT ?
    """
    rows = query_db(vitals_query, (patient_id, VITAL_HISTORY_LIMIT))
    if rows:
        latest_row = rows[0]
        result["vitals"] = _serialize_vitals_row(latest_row)
        result["vitals_history"] = [
            _serialize_vitals_row(row)
            for row in reversed(rows)
        ]
    else:
        result["vitals"] = None
        result["vitals_history"] = []

    # Diagnoses
    diag_query = """
        SELECT icd_title, icd_code 
        FROM diagnosis 
        WHERE subject_id = ?
    """
    rows = query_db(diag_query, (patient_id,))
    result["diagnoses"] = [
        {"title": row["icd_title"], "icd_code": row["icd_code"]}
        for row in rows
    ]

    # Medications
    med_query = """
        SELECT DISTINCT name, etcdescription 
        FROM medrecon 
        WHERE subject_id = ?
    """
    rows = query_db(med_query, (patient_id,))
    seen = set()
    meds = []
    for row in rows:
        name = row["name"]
        if name and name not in seen:
            seen.add(name)
            meds.append({
                "name": name,
                "description": row["etcdescription"] or "",
            })
    result["medications"] = meds

    return result


if __name__ == "__main__":
    # Test with patient ID 10002428
    test_patient = "10002428"
    print("=" * 60)
    print(f"Testing Patient Context Tools - Patient ID: {test_patient}")
    print("=" * 60)
    
    print("\n📊 VITALS:")
    print(get_patient_vitals.invoke(test_patient))
    
    print("\n🏥 DIAGNOSES:")
    print(get_patient_diagnoses.invoke(test_patient))
    
    print("\n💊 MEDICATIONS:")
    print(get_patient_meds.invoke(test_patient))
