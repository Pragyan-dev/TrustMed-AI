import psycopg2
from dotenv import load_dotenv
import os

load_dotenv()
DB_PASSWORD = '1234' # Hardcoded to be safe or could use os.getenv('DB_PASSWORD')

try:
    # 1. Connect to default 'postgres' to create the 'health' database
    conn = psycopg2.connect(
        host='localhost', 
        port='5432', 
        dbname='postgres', 
        user='postgres', 
        password=DB_PASSWORD
    )
    conn.autocommit = True
    cursor = conn.cursor()
    
    cursor.execute("SELECT 1 FROM pg_database WHERE datname='health'")
    if not cursor.fetchone():
        print("Creating database 'health'...")
        cursor.execute("CREATE DATABASE health")
    else:
        print("Database 'health' already exists.")
    
    cursor.close()
    conn.close()

    # 2. Connect to 'health' to populate it
    conn = psycopg2.connect(
        host='localhost', 
        port='5432', 
        dbname='health', 
        user='postgres', 
        password=DB_PASSWORD
    )
    cursor = conn.cursor()
    
    print("Populating database with setup_health_db.sql...")
    with open('setup_health_db.sql', 'r', encoding='utf-8') as f:
        sql_content = f.read()
    
    # Executing the SQL. Note: setup_health_db.sql has multiple statements.
    # psycopg2 can execute them if they are properly formatted.
    cursor.execute(sql_content)
    conn.commit()
    print("Database population successful.")
    
    cursor.close()
    conn.close()

except Exception as e:
    print(f"FAILED: {e}")
