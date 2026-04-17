import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()
try:
    # Try connecting to the default 'postgres' database
    conn = psycopg2.connect(
        host='localhost',
        port='5432',
        dbname='postgres',
        user='postgres',
        password='Nokia#3310'
    )
    print('CONNECTED_POSTGRES')
    cursor = conn.cursor()
    cursor.execute("SELECT datname FROM pg_database WHERE datname='health'")
    exists = cursor.fetchone()
    if exists:
        print('HEALTH_DB_EXISTS')
        cursor.close()
        conn.close()
        # Connect to health DB
        conn = psycopg2.connect(
            host='localhost',
            port='5432',
            dbname='health',
            user='postgres',
            password='Nokia#3310'
        )
        cursor = conn.cursor()
        cursor.execute("SELECT table_name FROM information_schema.tables WHERE table_schema='public'")
        tables = [r[0] for r in cursor.fetchall()]
        print(f'TABLES_IN_HEALTH: {tables}')
        if 'diseases' in tables:
            cursor.execute("SELECT COUNT(*) FROM diseases")
            print(f'DISEASES_COUNT: {cursor.fetchone()[0]}')
        conn.close()
    else:
        print('HEALTH_DB_MISSING')
        conn.close()
except Exception as e:
    print(f'ERROR: {e}')
