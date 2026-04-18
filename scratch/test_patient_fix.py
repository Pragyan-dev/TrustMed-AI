
import os
import sys
# Add project root to path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, PROJECT_ROOT)

from src.patient_context_tool import get_patient_data_json

def test():
    patient_id = "10007058"
    print(f"Testing patient data for ID: {patient_id}")
    try:
        data = get_patient_data_json(patient_id)
        print("Vitals:", data.get("vitals"))
        print("Diagnoses count:", len(data.get("diagnoses", [])))
        print("Medications count:", len(data.get("medications", [])))
    except Exception as e:
        print(f"Error: {e}")

if __name__ == "__main__":
    test()
