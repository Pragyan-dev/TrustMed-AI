import sqlite3
import os

# Create data directory if it doesn't exist
os.makedirs("data", exist_ok=True)
db_path = "data/mimic_demo.db"

conn = sqlite3.connect(db_path)
cursor = conn.cursor()

# Create tables
cursor.execute("""
CREATE TABLE IF NOT EXISTS vitalsign (
    subject_id TEXT,
    temperature REAL,
    heartrate REAL,
    resprate REAL,
    o2sat REAL,
    sbp REAL,
    dbp REAL,
    charttime TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS diagnosis (
    subject_id TEXT,
    icd_title TEXT,
    icd_code TEXT
)
""")

cursor.execute("""
CREATE TABLE IF NOT EXISTS medrecon (
    subject_id TEXT,
    name TEXT,
    etcdescription TEXT
)
""")

# Sample data for patient 10002428
patients = ["10002428", "10025463", "10027602", "10009049"]

for pid in patients:
    # Vitals
    cursor.execute("INSERT INTO vitalsign VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
                   (pid, 98.6, 72, 16, 98, 120, 80, "2024-04-16 08:00:00"))
    # Diagnosis
    cursor.execute("INSERT INTO diagnosis VALUES (?, ?, ?)",
                   (pid, "Essential (primary) hypertension", "I10"))
    # Medication
    cursor.execute("INSERT INTO medrecon VALUES (?, ?, ?)",
                   (pid, "Lisinopril", "Used for high blood pressure"))

conn.commit()
conn.close()
print(f"Sample database created at: {os.path.abspath(db_path)}")
