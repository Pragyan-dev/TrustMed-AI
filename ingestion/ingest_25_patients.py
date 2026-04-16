import sqlite3
import pandas as pd
import random
import os
from datetime import datetime

# Path management
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DB_PATH = os.path.join(PROJECT_ROOT, 'data', 'mimic_demo.db')
CSV_PATH = os.path.join(PROJECT_ROOT, 'data', 'mimic_cxr', 'subset_labels.csv')

def get_clinical_context(labels):
    """Returns realistic vitals and meds based on X-ray labels."""
    vitals = {
        'heartrate': 75,
        'sbp': 120,
        'dbp': 80,
        'temperature': 98.6,
        'o2sat': 98,
        'resprate': 16
    }
    meds = []
    
    label_str = labels.lower()
    
    if 'pneumonia' in label_str or 'consolidation' in label_str:
        vitals['temperature'] = round(random.uniform(100.5, 102.8), 1)
        vitals['heartrate'] = random.randint(90, 115)
        vitals['o2sat'] = random.randint(88, 94)
        vitals['resprate'] = random.randint(22, 28)
        meds.append(('Ceftriaxone', '1g IV daily'))
        meds.append(('Azithromycin', '500mg PO daily'))
        
    if 'edema' in label_str or 'effusion' in label_str or 'cardiomegaly' in label_str:
        vitals['sbp'] = random.randint(140, 180)
        vitals['dbp'] = random.randint(90, 110)
        vitals['heartrate'] = random.randint(85, 110)
        meds.append(('Furosemide', '40mg IV BID'))
        if 'cardiomegaly' in label_str:
            meds.append(('Lisinopril', '10mg PO daily'))
            
    if 'atelectasis' in label_str or 'pneumothorax' in label_str:
        vitals['o2sat'] = random.randint(90, 95)
        vitals['heartrate'] = random.randint(95, 110)
        vitals['resprate'] = random.randint(20, 24)
        
    if not meds:
        meds.append(('Aspirin', '81mg PO daily'))
        
    return vitals, meds

def main():
    if not os.path.exists(CSV_PATH):
        print(f"Error: {CSV_PATH} not found.")
        return

    print(f"Reading labels from {CSV_PATH}...")
    df = pd.read_csv(CSV_PATH)
    
    unique_ids = df['subject_id'].unique()[:25]
    print(f"Found {len(unique_ids)} patients to ingest.")
    
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    for sid in unique_ids:
        # Convert to string as required by the text NOT NULL constraint if subject_id is text
        # although pandas unique() might give numpy types.
        sid_str = str(int(sid))
        
        patient_labels = df[df['subject_id'] == sid].iloc[0]['labels']
        print(f"Ingesting Patient {sid_str} (Labels: {patient_labels})")
        
        # 1. Insert Diagnosis
        cursor.execute("DELETE FROM diagnosis WHERE subject_id = ?", (sid_str,))
        for label in patient_labels.split('|'):
            cursor.execute("INSERT INTO diagnosis (subject_id, icd_code, icd_title) VALUES (?, ?, ?)",
                         (sid_str, 'V-CXR', label.strip()))
            
        # 2. Generate and Insert Vitals
        cursor.execute("DELETE FROM vitalsign WHERE subject_id = ?", (sid_str,))
        v = get_clinical_context(patient_labels)[0]
        cursor.execute("""
            INSERT INTO vitalsign (subject_id, charttime, temperature, heartrate, resprate, o2sat, sbp, dbp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (sid_str, datetime.now().strftime('%Y-%m-%d %H:%M:%S'), 
             v['temperature'], v['heartrate'], v['resprate'], v['o2sat'], v['sbp'], v['dbp']))
        
        # 3. Insert Medications
        cursor.execute("DELETE FROM medrecon WHERE subject_id = ?", (sid_str,))
        _, meds = get_clinical_context(patient_labels)
        for m_name, m_desc in meds:
            cursor.execute("""
                INSERT INTO medrecon (subject_id, name, etcdescription)
                VALUES (?, ?, ?)
            """, (sid_str, m_name, m_desc))
            
    conn.commit()
    conn.close()
    print(f"Ingestion of 25 patients into {DB_PATH} complete.")

if __name__ == "__main__":
    main()
