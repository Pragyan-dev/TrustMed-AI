
import os
import sys
import sqlite3

# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.patient_context_tool import query_db, get_patient_data_json

def debug_patient(patient_id):
    print(f"--- Debugging Patient: {patient_id} ---")

    # 1. Test raw query_db for diagnoses
    diag_query = "SELECT icd_title, icd_code FROM diagnosis WHERE subject_id = ?"
    rows = query_db(diag_query, (patient_id,))
    print(f"Raw diagnosis rows found: {len(rows)}")
    for i, row in enumerate(rows):
        print(f"  Row {i}: title='{row['icd_title']}', code='{row['icd_code']}'")

    # 2. Test full get_patient_data_json
    try:
        data = get_patient_data_json(patient_id)
        print(f"Data vitals: {data.get('vitals') is not None}")
        print(f"Data diagnoses count: {len(data.get('diagnoses', []))}")
        print(f"Data medications count: {len(data.get('medications', []))}")

        has_data = data.get("vitals") or data.get("diagnoses") or data.get("medications")
        print(f"Final check (has_data): {bool(has_data)}")
    except Exception as e:
        print(f"Error in get_patient_data_json: {e}")

if __name__ == "__main__":
    debug_patient("10027602")
    # Also test with integer just in case
    # debug_patient(10027602)
