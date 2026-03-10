"""
MIMIC Demo Data → SQLite Ingestion

This script loads MIMIC CSV files into a local SQLite database
for efficient querying by the AI agent.
"""

import pandas as pd
import sqlite3
import os

# Configuration
DATA_DIR = "./archive 2"
DB_PATH = "./mimic_demo.db"

# List of MIMIC CSV files to ingest
CSV_FILES = [
    "triage.csv",
    "vitalsign.csv",
    "edstays.csv",
    "diagnosis.csv",
    "medrecon.csv",
    "pyxis.csv"
]


def clean_column_names(df):
    """Convert column names to lowercase and strip whitespace."""
    df.columns = [col.lower().strip() for col in df.columns]
    return df


def ingest_csv_to_sqlite():
    """Load all CSV files into SQLite database."""
    print("=" * 60)
    print("MIMIC CSV → SQLite Ingestion")
    print("=" * 60)
    
    # Connect to SQLite (creates file if it doesn't exist)
    conn = sqlite3.connect(DB_PATH)
    
    loaded_tables = []
    
    for filename in CSV_FILES:
        filepath = os.path.join(DATA_DIR, filename)
        table_name = os.path.splitext(filename)[0]  # Remove .csv extension
        
        print(f"\n📄 Processing: {filename}")
        
        if not os.path.exists(filepath):
            print(f"  ⚠ File not found, skipping")
            continue
        
        try:
            # Read CSV into DataFrame
            df = pd.read_csv(filepath)
            
            # Clean column names
            df = clean_column_names(df)
            
            # Save to SQLite
            df.to_sql(table_name, conn, if_exists='replace', index=False)
            
            loaded_tables.append(table_name)
            print(f"  ✓ Loaded {len(df):,} rows into table '{table_name}'")
            print(f"  ✓ Columns: {list(df.columns)}")
            
        except Exception as e:
            print(f"  ❌ Error loading {filename}: {e}")
    
    # Verification: List all tables
    print("\n" + "=" * 60)
    print("VERIFICATION")
    print("=" * 60)
    
    cursor = conn.execute("SELECT name FROM sqlite_master WHERE type='table';")
    tables = [row[0] for row in cursor.fetchall()]
    print(f"\n📊 Tables in database: {tables}")
    
    # Print first 3 rows of diagnosis table
    if 'diagnosis' in tables:
        print(f"\n📋 Sample from 'diagnosis' table (first 3 rows):")
        sample_df = pd.read_sql("SELECT * FROM diagnosis LIMIT 3", conn)
        print(sample_df.to_string(index=False))
    
    conn.close()
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"✓ Database created: {os.path.abspath(DB_PATH)}")
    print(f"✓ Tables loaded: {len(loaded_tables)}")
    for table in loaded_tables:
        print(f"  - {table}")
    print("=" * 60)


if __name__ == "__main__":
    ingest_csv_to_sqlite()
