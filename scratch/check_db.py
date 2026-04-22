import os

import psycopg2
from dotenv import load_dotenv

load_dotenv()

DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")
DB_NAME = os.getenv("DB_NAME", "health")
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "1234")


try:
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname="postgres",
        user=DB_USER,
        password=DB_PASSWORD,
    )
    print("CONNECTED_POSTGRES")
    cursor = conn.cursor()
    cursor.execute("SELECT datname FROM pg_database WHERE datname=%s", (DB_NAME,))
    exists = cursor.fetchone()
    if exists:
        print(f"{DB_NAME.upper()}_DB_EXISTS")
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
        cursor.execute(
            "SELECT table_name FROM information_schema.tables WHERE table_schema='public'"
        )
        tables = [row[0] for row in cursor.fetchall()]
        print(f"TABLES_IN_{DB_NAME.upper()}: {tables}")
        if "diseases" in tables:
            cursor.execute("SELECT COUNT(*) FROM diseases")
            print(f"DISEASES_COUNT: {cursor.fetchone()[0]}")
        conn.close()
    else:
        print(f"{DB_NAME.upper()}_DB_MISSING")
        conn.close()
except Exception as exc:
    print(f"ERROR: {exc}")
