import os
from pathlib import Path

import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "health")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "1234")
SQL_PATH = Path(__file__).resolve().parents[1] / "setup_health_db.sql"


try:
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname="postgres",
        user=DB_USER,
        password=DB_PASSWORD,
    )
    conn.autocommit = True
    cursor = conn.cursor()

    cursor.execute("SELECT 1 FROM pg_database WHERE datname=%s", (DB_NAME,))
    if not cursor.fetchone():
        print(f"Creating database '{DB_NAME}'...")
        cursor.execute(f"CREATE DATABASE {DB_NAME}")
    else:
        print(f"Database '{DB_NAME}' already exists.")

    cursor.close()
    conn.close()

    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )
    cursor = conn.cursor()

    print(f"Populating database with {SQL_PATH.name}...")
    with SQL_PATH.open("r", encoding="utf-8") as handle:
        sql_content = handle.read()

    cursor.execute(sql_content)
    conn.commit()
    print("Database population successful.")

    cursor.close()
    conn.close()
except Exception as exc:
    print(f"FAILED: {exc}")
