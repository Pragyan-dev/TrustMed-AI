import sqlite3
import pandas as pd
import os
from datetime import datetime

# Path management
_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
PROJECT_ROOT = os.path.dirname(_SCRIPT_DIR)
DATA_DIR = os.path.join(PROJECT_ROOT, 'data')
ARCHIVE_DIR = os.path.join(DATA_DIR, 'archive')
DB_PATH = os.path.join(DATA_DIR, 'mimic_demo.db')
SUBSET_CSV = os.path.join(DATA_DIR, 'mimic_cxr', 'subset_labels.csv')

def ingest_actual_data():
    if not os.path.exists(DB_PATH):
        print(f"Error: {DB_PATH} not found. Please run create_demo_db.py first.")
        return

    if not os.path.exists(SUBSET_CSV):
        print(f"Error: {SUBSET_CSV} not found.")
        return

    # 1. Identify target patients (first 25 from subset)
    print(f"Reading target patients from {SUBSET_CSV}...")
    subset_df = pd.read_csv(SUBSET_CSV)
    unique_ids = subset_df['subject_id'].unique()[:25]
    unique_ids_str = [str(int(sid)) for sid in unique_ids]
    print(f"Targeting {len(unique_ids_str)} patients.")

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()

    # Clear existing demo data for these patients if needed, 
    # but we'll just clear everything if we want a fresh start or just update these.
    # The user asked to update the data being used.
    
    # 2. Process Vitals
    vitals_csv = os.path.join(ARCHIVE_DIR, 'vitalsign.csv')
    if os.path.exists(vitals_csv):
        print(f"Ingesting vitals from {vitals_csv}...")
        vitals_df = pd.read_csv(vitals_csv)
        # Filter for our patients
        vitals_subset = vitals_df[vitals_df['subject_id'].astype(str).isin(unique_ids_str)]
        
        # Clear existing
        for sid in unique_ids_str:
            cursor.execute("DELETE FROM vitalsign WHERE subject_id = ?", (sid,))
        
        # Insert
        # Schema: subject_id, temperature, heartrate, resprate, o2sat, sbp, dbp, charttime
        for _, row in vitals_subset.iterrows():
            cursor.execute("""
                INSERT INTO vitalsign (subject_id, temperature, heartrate, resprate, o2sat, sbp, dbp, charttime)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (str(int(row['subject_id'])), row['temperature'], row['heartrate'], 
                 row['resprate'], row['o2sat'], row['sbp'], row['dbp'], row['charttime']))
        print(f"  Inserted {len(vitals_subset)} vital sign records.")
    else:
        print(f"Warning: {vitals_csv} not found.")

    # 3. Process Diagnoses
    diag_csv = os.path.join(ARCHIVE_DIR, 'diagnosis.csv')
    if os.path.exists(diag_csv):
        print(f"Ingesting diagnoses from {diag_csv}...")
        diag_df = pd.read_csv(diag_csv)
        diag_subset = diag_df[diag_df['subject_id'].astype(str).isin(unique_ids_str)]
        
        for sid in unique_ids_str:
            cursor.execute("DELETE FROM diagnosis WHERE subject_id = ?", (sid,))
            
        for _, row in diag_subset.iterrows():
            cursor.execute("""
                INSERT INTO diagnosis (subject_id, icd_code, icd_title)
                VALUES (?, ?, ?)
            """, (str(int(row['subject_id'])), row['icd_code'], row['icd_title']))
        print(f"  Inserted {len(diag_subset)} diagnosis records.")
    else:
        print(f"Warning: {diag_csv} not found.")

    # 4. Process Meds
    med_csv = os.path.join(ARCHIVE_DIR, 'medrecon.csv')
    if os.path.exists(med_csv):
        print(f"Ingesting medrecon from {med_csv}...")
        med_df = pd.read_csv(med_csv)
        med_subset = med_df[med_df['subject_id'].astype(str).isin(unique_ids_str)]
        
        for sid in unique_ids_str:
            cursor.execute("DELETE FROM medrecon WHERE subject_id = ?", (sid,))
            
        for _, row in med_subset.iterrows():
            # Schema: subject_id, name, etcdescription
            # actual csv has name and etcdescription (sometimes empty)
            cursor.execute("""
                INSERT INTO medrecon (subject_id, name, etcdescription)
                VALUES (?, ?, ?)
            """, (str(int(row['subject_id'])), row['name'], row['etcdescription'] if pd.notna(row['etcdescription']) else ""))
        print(f"  Inserted {len(med_subset)} medication records.")
    else:
        print(f"Warning: {med_csv} not found.")

    conn.commit()
    conn.close()
    print("Ingestion complete.")

if __name__ == "__main__":
    ingest_actual_data()
