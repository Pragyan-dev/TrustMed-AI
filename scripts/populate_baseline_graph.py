import os
import re
from dotenv import load_dotenv
from neo4j import GraphDatabase

load_dotenv()

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")

if not NEO4J_URI or not NEO4J_PASSWORD:
    print("❌ Error: NEO4J_URI or NEO4J_PASSWORD not found in .env")
    exit(1)

def parse_sql_data(file_path):
    """
    Primitive SQL parser to extract disease and symptom data from setup_health_db.sql
    """
    with open(file_path, 'r') as f:
        content = f.read()
    
    # Extract tuples from the INSERT statement
    # Each tuple looks like: ('Name', 'URL', 'Desc', 'Symptoms', ...)
    diseases = []
    
    # Simple regex to find the content between parentheses in the VALUES part
    value_tuples = re.findall(r"\(\s*'(.*?)',\s*'(.*?)',\s*'(.*?)',\s*'(.*?)'", content, re.DOTALL)
    
    for match in value_tuples:
        name, url, desc, symptoms_str = match
        # Clean symptoms
        symptoms = [s.strip() for s in symptoms_str.split(',') if s.strip()]
        diseases.append({
            "name": name,
            "url": url,
            "description": desc,
            "symptoms": symptoms
        })
    
    # Filter to only keep rows that looks like diseases (names are Usually the first field)
    # The setup_health_db.sql has multiple inserts (medicines, symptoms, diseases).
    # We want the ones that came after "INSERT INTO diseases"
    disease_section = content.split("INSERT INTO diseases")[1].split(";")[0]
    final_diseases = []
    matches = re.findall(r"\(\s*'(.*?)',\s*'(.*?)',\s*'(.*?)',\s*'(.*?)'", disease_section, re.DOTALL)
    for m in matches:
        name, url, desc, symptoms_str = m
        final_diseases.append({
            "name": name,
            "url": url,
            "description": desc,
            "symptoms": [s.strip() for s in symptoms_str.split(',') if s.strip()]
        })
        
    return final_diseases

def populate_neo4j(diseases):
    print(f"🚀 Connecting to Neo4j at {NEO4J_URI}...")
    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USERNAME, NEO4J_PASSWORD))
    
    try:
        with driver.session() as session:
            # 1. Clear existing constraints/data (Optional, but clean)
            session.run("MATCH (n) DETACH DELETE n")
            
            # 2. Create Disease and Symptom nodes
            print(f"📊 Loading {len(diseases)} diseases into graph...")
            for disease in diseases:
                # Create Disease
                session.run("""
                    MERGE (d:Disease {name: $name})
                    SET d.url = $url, d.description = $description
                """, name=disease["name"], url=disease["url"], description=disease["description"])
                
                # Create Symptoms and Relationships
                for symptom_name in disease["symptoms"]:
                    # Clean the name (remove leading "and ", dots, etc)
                    clean_symptom = re.sub(r'^(and|or)\s+', '', symptom_name, flags=re.IGNORECASE)
                    clean_symptom = clean_symptom.strip(' .')
                    
                    if len(clean_symptom) > 2:
                        session.run("""
                            MATCH (d:Disease {name: $d_name})
                            MERGE (s:Symptom {name: $s_name})
                            MERGE (d)-[:HAS_SYMPTOM]->(s)
                        """, d_name=disease["name"], s_name=clean_symptom)
                        
            print("✅ Graph population complete!")
            
    except Exception as e:
        print(f"❌ Neo4j Error: {e}")
    finally:
        driver.close()

if __name__ == "__main__":
    sql_path = "setup_health_db.sql"
    if not os.path.exists(sql_path):
        print(f"❌ Error: {sql_path} not found")
        exit(1)
        
    print("🔍 Parsing medical data from SQL...")
    data = parse_sql_data(sql_path)
    if not data:
        print("⚠️ No disease data found in SQL file. Check parser regex.")
    else:
        populate_neo4j(data)
