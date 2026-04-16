"""
TrustMed-AI: Create Demo SQLite Database
=========================================
Creates data/mimic_demo.db with the tables expected by patient_context_tool.py:
  - vitalsign   (subject_id, temperature, heartrate, resprate, o2sat, sbp, dbp, charttime)
  - diagnosis   (subject_id, icd_code, icd_title)
  - medrecon    (subject_id, name, etcdescription)

Includes 3 pre-built demo patients matching the test cases in the run guide.
"""

import os
import sqlite3

PROJECT_ROOT = os.path.dirname(os.path.abspath(__file__))
DATA_DIR = os.path.join(PROJECT_ROOT, "data")
DB_PATH = os.path.join(DATA_DIR, "mimic_demo.db")

os.makedirs(DATA_DIR, exist_ok=True)

print(f"Creating database at: {DB_PATH}")

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

# ─── Create Tables ───────────────────────────────────────────────────────────

c.executescript("""
DROP TABLE IF EXISTS vitalsign;
CREATE TABLE vitalsign (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id  TEXT NOT NULL,
    temperature REAL,
    heartrate   REAL,
    resprate    REAL,
    o2sat       REAL,
    sbp         REAL,
    dbp         REAL,
    charttime   TEXT DEFAULT '2026-03-28 01:00:00'
);

DROP TABLE IF EXISTS diagnosis;
CREATE TABLE diagnosis (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id  TEXT NOT NULL,
    icd_code    TEXT,
    icd_title   TEXT
);

DROP TABLE IF EXISTS medrecon;
CREATE TABLE medrecon (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    subject_id     TEXT NOT NULL,
    name           TEXT,
    etcdescription TEXT
);
""")

# ─── Patient 99900001: Heart Failure + CAD + HTN ──────────────────────────────

c.executemany("INSERT INTO vitalsign (subject_id, heartrate, sbp, dbp, resprate, temperature, o2sat, charttime) VALUES (?,?,?,?,?,?,?,?)", [
    ("99900001", 105, 155, 95, 24, 98.8, 91, "2026-03-28 00:30:00"),
    ("99900001", 102, 148, 90, 22, 98.6, 93, "2026-03-27 18:00:00"),
    ("99900001", 98,  142, 88, 20, 98.5, 94, "2026-03-27 12:00:00"),
])

c.executemany("INSERT INTO diagnosis (subject_id, icd_code, icd_title) VALUES (?,?,?)", [
    ("99900001", "I509",  "Heart failure, unspecified"),
    ("99900001", "I2510", "Atherosclerotic heart disease of native coronary artery without angina pectoris"),
    ("99900001", "I10",   "Essential (primary) hypertension"),
    ("99900001", "E785",  "Hyperlipidemia, unspecified"),
])

c.executemany("INSERT INTO medrecon (subject_id, name, etcdescription) VALUES (?,?,?)", [
    ("99900001", "Lisinopril",          "ACE inhibitor — 20 mg PO daily"),
    ("99900001", "Atorvastatin",        "Statin — 40 mg PO daily"),
    ("99900001", "Metoprolol Tartrate", "Beta-blocker — 50 mg PO twice daily"),
    ("99900001", "Furosemide",          "Loop diuretic — 40 mg PO daily"),
    ("99900001", "Aspirin",             "Antiplatelet — 81 mg PO daily"),
])

# ─── Patient 99900002: Bacterial Pneumonia + Pleural Effusion ────────────────

c.executemany("INSERT INTO vitalsign (subject_id, heartrate, sbp, dbp, resprate, temperature, o2sat, charttime) VALUES (?,?,?,?,?,?,?,?)", [
    ("99900002", 115, 110, 65, 28, 102.6, 88, "2026-03-28 00:30:00"),
    ("99900002", 120, 105, 60, 30, 103.1, 86, "2026-03-27 18:00:00"),
    ("99900002", 108, 115, 70, 26, 101.5, 90, "2026-03-27 12:00:00"),
])

c.executemany("INSERT INTO diagnosis (subject_id, icd_code, icd_title) VALUES (?,?,?)", [
    ("99900002", "J159", "Unspecified bacterial pneumonia"),
    ("99900002", "J90",  "Pleural effusion, not elsewhere classified"),
    ("99900002", "E860", "Dehydration"),
])

c.executemany("INSERT INTO medrecon (subject_id, name, etcdescription) VALUES (?,?,?)", [
    ("99900002", "Ceftriaxone",      "3rd-gen cephalosporin antibiotic — 1g IV every 24 hours"),
    ("99900002", "Azithromycin",     "Macrolide antibiotic — 500 mg IV every 24 hours"),
    ("99900002", "Acetaminophen",    "Antipyretic/analgesic — 650 mg PO every 6 hours PRN"),
    ("99900002", "Albuterol Inhaler","Bronchodilator — 90 mcg inhaled every 4 hours PRN"),
])

# ─── Patient 99900003: Hypertensive Heart Failure + COPD + Pneumonia ─────────

c.executemany("INSERT INTO vitalsign (subject_id, heartrate, sbp, dbp, resprate, temperature, o2sat, charttime) VALUES (?,?,?,?,?,?,?,?)", [
    ("99900003", 98, 165, 90, 22, 99.3, 93, "2026-03-28 00:30:00"),
    ("99900003", 95, 160, 88, 21, 99.0, 94, "2026-03-27 18:00:00"),
    ("99900003", 92, 155, 85, 20, 98.8, 95, "2026-03-27 12:00:00"),
])

c.executemany("INSERT INTO diagnosis (subject_id, icd_code, icd_title) VALUES (?,?,?)", [
    ("99900003", "I110", "Hypertensive heart disease with heart failure"),
    ("99900003", "J449", "Chronic obstructive pulmonary disease, unspecified"),
    ("99900003", "J189", "Pneumonia, unspecified organism"),
])

c.executemany("INSERT INTO medrecon (subject_id, name, etcdescription) VALUES (?,?,?)", [
    ("99900003", "Amlodipine",             "Calcium channel blocker — 10 mg PO daily"),
    ("99900003", "Budesonide-Formoterol",  "ICS/LABA inhaler for COPD — 160/4.5 mcg inhaled twice daily"),
    ("99900003", "Levofloxacin",           "Fluoroquinolone antibiotic — 750 mg IV every 24 hours"),
    ("99900003", "Furosemide",             "Loop diuretic (IV) — 20 mg IV every 12 hours"),
])

conn.commit()
conn.close()

# ─── Verify ──────────────────────────────────────────────────────────────────

conn = sqlite3.connect(DB_PATH)
c = conn.cursor()

print("\n✅ Database created successfully!\n")
for table in ["vitalsign", "diagnosis", "medrecon"]:
    c.execute(f"SELECT COUNT(*) FROM {table}")
    count = c.fetchone()[0]
    print(f"  {table}: {count} rows")

print("\nDemo patients loaded:")
for pid in ["99900001", "99900002", "99900003"]:
    c.execute("SELECT icd_title FROM diagnosis WHERE subject_id=?", (pid,))
    diagnoses = [r[0] for r in c.fetchall()]
    print(f"  Patient {pid}: {', '.join(diagnoses)}")

conn.close()
print(f"\nDatabase path: {DB_PATH}")
