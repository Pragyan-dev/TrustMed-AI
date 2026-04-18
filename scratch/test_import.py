
import sys
import os
# Mock enough of main.py to test get_medical_explanation
sys.path.insert(0, os.path.join(os.getcwd(), "api"))
try:
    from medical_dictionary import get_medical_explanation
    print("Import success")
    res = get_medical_explanation("pneumonia")
    print(f"Result: {res}")
except Exception as e:
    print(f"Error: {e}")
    import traceback
    traceback.print_exc()
