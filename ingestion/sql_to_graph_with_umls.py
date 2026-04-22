import os
import time
from neo4j import GraphDatabase
from src.umls_client import UMLSClient
from ingestion.sql_to_chroma import get_connection, fetch_all_rows
from dotenv import load_dotenv

load_dotenv()

# ----------------------------
# CONFIG
# ----------------------------
NEO4J_URI = os.environ.get("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.environ.get("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD", "password")

UMLS_API_KEY = os.environ.get("UMLS_API_KEY")

class Neo4jPipeline:
    def __init__(self, uri, user, password):
        self.driver = GraphDatabase.driver(uri, auth=(user, password))
        self.umls = UMLSClient(api_key=UMLS_API_KEY)

    def close(self):
        self.driver.close()

    def process_diseases(self):
        print("\n--- Processing Diseases ---")
        conn = get_connection()
        try:
            diseases = fetch_all_rows(conn, "diseases", ["name", "description", "main_url"])
            with self.driver.session() as session:
                for row in diseases:
                    name = row['name']
                    print(f"Validating term: {name}...")
                    result = self.umls.get_cui(name)
                    
                    if result:
                        cui, umls_name = result
                        print(f"Found valid medical term: {name} -> {cui} ({umls_name})")
                        session.run("""
                            MERGE (d:Disease {name: $name})
                            SET d.cui = $cui,
                                d.description = $description,
                                d.url = $url,
                                d.last_updated = timestamp()
                        """, cui=cui, name=name, description=row['description'], url=row['main_url'])
                    else:
                        print(f"Skipping unverified term: {name}")
        finally:
            conn.close()

    def process_symptoms(self):
        print("\n--- Processing Symptoms ---")
        conn = get_connection()
        try:
            symptoms_data = fetch_all_rows(conn, "symptoms", ["disease_name", "symptoms"])
            with self.driver.session() as session:
                for row in symptoms_data:
                    disease_name = row['disease_name']
                    # Get CUI for the disease
                    disease_result = self.umls.get_cui(disease_name)
                    if not disease_result:
                        print(f"Skipping symptoms for unverified disease: {disease_name}")
                        continue
                        
                    disease_cui, _ = disease_result
                    
                    # Split symptoms by comma
                    raw_symptoms = row.get('symptoms', '')
                    if not raw_symptoms:
                        continue
                        
                    symptom_list = [s.strip() for s in raw_symptoms.split(',') if s.strip()]
                    
                    for s_name in symptom_list:
                        print(f"Validating symptom: {s_name}...")
                        s_result = self.umls.get_cui(s_name)
                        
                        if s_result:
                            s_cui, s_umls_name = s_result
                            print(f"Linking: {disease_name} -[:HAS_SYMPTOM]-> {s_umls_name} ({s_cui})")
                            session.run("""
                                MATCH (d:Disease {name: $disease_name})
                                MERGE (s:Symptom {name: $symptom_name})
                                SET s.cui = $symptom_cui
                                MERGE (d)-[:HAS_SYMPTOM]->(s)
                            """, disease_name=disease_name, symptom_cui=s_cui, symptom_name=s_name)
                        else:
                            print(f"Skipping unverified symptom: {s_name}")
        finally:
            conn.close()

if __name__ == "__main__":
    pipeline = Neo4jPipeline(NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD)
    try:
        pipeline.process_diseases()
        pipeline.process_symptoms()
        print("\nETL Pipeline completed successfully.")
    except Exception as e:
        print(f"An error occurred: {e}")
    finally:
        pipeline.close()
