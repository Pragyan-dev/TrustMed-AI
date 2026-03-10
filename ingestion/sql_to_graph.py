#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
SQL to Neo4j Knowledge Graph Pipeline

This script:
1. Connects to PostgreSQL and fetches disease data
2. Uses spaCy's biomedical NER model (en_ner_bc5cdr_md) to extract entities
3. Creates Disease nodes and Symptom nodes in Neo4j
4. Links them with HAS_SYMPTOM relationships

Uses the same database connection logic as sql_to_chroma.py
"""

import psycopg2
from psycopg2.extras import RealDictCursor
from typing import List, Dict, Any, Set, Tuple
from neo4j import GraphDatabase
import spacy

# ----------------------------
# POSTGRESQL CONFIG (from sql_to_chroma.py)
# ----------------------------

DB_HOST = "localhost"
DB_PORT = 5432
DB_NAME = "health"
DB_USER = "postgres"
DB_PASSWORD = "Nokia#3310"

# ----------------------------
# NEO4J CONFIG
# ----------------------------

NEO4J_URI = "neo4j+s://dbde172c.databases.neo4j.io"
NEO4J_USERNAME = "neo4j"
NEO4J_PASSWORD = "YhBsHCJzwQMVvyFdhDWl_2nM0NQRSXb7AYkYXKnMViM"

# ----------------------------
# HELPER FUNCTIONS (from sql_to_chroma.py)
# ----------------------------

def get_connection():
    """Connect to PostgreSQL database."""
    conn = psycopg2.connect(
        host=DB_HOST,
        port=DB_PORT,
        dbname=DB_NAME,
        user=DB_USER,
        password=DB_PASSWORD,
    )
    return conn


def fetch_all_rows(conn, table: str, columns: List[str]) -> List[Dict[str, Any]]:
    """
    Fetch all rows for a given table, returning them as dicts.
    """
    with conn.cursor(cursor_factory=RealDictCursor) as cur:
        col_list = ", ".join(columns)
        query = f"SELECT {col_list} FROM {table};"
        cur.execute(query)
        rows = cur.fetchall()
    return rows


# ----------------------------
# SPACY NER EXTRACTION
# ----------------------------

def load_ner_model():
    """Load the biomedical NER model."""
    try:
        nlp = spacy.load("en_ner_bc5cdr_md")
        print("Loaded spaCy model: en_ner_bc5cdr_md")
        return nlp
    except OSError:
        print("Model not found. Installing en_ner_bc5cdr_md...")
        import subprocess
        subprocess.run(["pip", "install", "https://s3-us-west-2.amazonaws.com/ai2-s2-scispacy/releases/v0.5.4/en_ner_bc5cdr_md-0.5.4.tar.gz"], check=True)
        nlp = spacy.load("en_ner_bc5cdr_md")
        print("Installed and loaded spaCy model: en_ner_bc5cdr_md")
        return nlp


def extract_entities(nlp, text: str) -> List[Tuple[str, str]]:
    """
    Extract named entities from text using the biomedical NER model.
    Returns list of (entity_text, entity_label) tuples.
    
    The en_ner_bc5cdr_md model extracts:
    - DISEASE: Disease entities
    - CHEMICAL: Chemical/Drug entities
    """
    if not text or not isinstance(text, str):
        return []
    
    doc = nlp(text)
    entities = []
    seen = set()
    
    for ent in doc.ents:
        # Normalize entity text
        entity_text = ent.text.strip().lower()
        entity_label = ent.label_
        
        # Skip duplicates and very short entities
        if entity_text and len(entity_text) > 2 and entity_text not in seen:
            entities.append((ent.text.strip(), entity_label))
            seen.add(entity_text)
    
    return entities


# ----------------------------
# NEO4J OPERATIONS
# ----------------------------

class Neo4jConnection:
    """Neo4j database connection handler."""
    
    def __init__(self, uri: str, username: str, password: str):
        self.driver = GraphDatabase.driver(uri, auth=(username, password))
        print(f"Connected to Neo4j at {uri}")
    
    def close(self):
        self.driver.close()
        print("Neo4j connection closed")
    
    def verify_connection(self):
        """Verify the connection is working."""
        with self.driver.session() as session:
            result = session.run("RETURN 1 AS num")
            record = result.single()
            if record and record["num"] == 1:
                print("Neo4j connection verified successfully!")
                return True
        return False
    
    def create_constraints(self):
        """Create uniqueness constraints for better performance."""
        with self.driver.session() as session:
            # Create constraint for Disease nodes
            try:
                session.run("""
                    CREATE CONSTRAINT disease_name IF NOT EXISTS
                    FOR (d:Disease) REQUIRE d.name IS UNIQUE
                """)
                print("Created constraint for Disease.name")
            except Exception as e:
                print(f"Constraint for Disease may already exist: {e}")
            
            # Create constraint for Symptom nodes
            try:
                session.run("""
                    CREATE CONSTRAINT symptom_name IF NOT EXISTS
                    FOR (s:Symptom) REQUIRE s.name IS UNIQUE
                """)
                print("Created constraint for Symptom.name")
            except Exception as e:
                print(f"Constraint for Symptom may already exist: {e}")
    
    def create_disease_node(self, disease: Dict[str, Any]) -> None:
        """Create or merge a Disease node."""
        with self.driver.session() as session:
            session.run("""
                MERGE (d:Disease {name: $name})
                ON CREATE SET 
                    d.source_url = $source_url,
                    d.description = $description,
                    d.causes = $causes,
                    d.diagnosis = $diagnosis,
                    d.prevention = $prevention,
                    d.treatment = $treatment,
                    d.living_with = $living_with,
                    d.created_at = datetime()
                ON MATCH SET
                    d.updated_at = datetime()
            """, 
            name=disease.get("name", "Unknown"),
            source_url=disease.get("main_url", ""),
            description=disease.get("description", ""),
            causes=disease.get("causes", ""),
            diagnosis=disease.get("diagnosis", ""),
            prevention=disease.get("prevention", ""),
            treatment=disease.get("treatment", ""),
            living_with=disease.get("living_with", "")
            )
    
    def create_symptom_node(self, symptom_name: str, entity_type: str) -> None:
        """Create or merge a Symptom node."""
        with self.driver.session() as session:
            session.run("""
                MERGE (s:Symptom {name: $name})
                ON CREATE SET 
                    s.entity_type = $entity_type,
                    s.created_at = datetime()
            """,
            name=symptom_name,
            entity_type=entity_type
            )
    
    def create_has_symptom_relationship(self, disease_name: str, symptom_name: str) -> None:
        """Create HAS_SYMPTOM relationship between Disease and Symptom."""
        with self.driver.session() as session:
            session.run("""
                MATCH (d:Disease {name: $disease_name})
                MATCH (s:Symptom {name: $symptom_name})
                MERGE (d)-[r:HAS_SYMPTOM]->(s)
                ON CREATE SET r.created_at = datetime()
            """,
            disease_name=disease_name,
            symptom_name=symptom_name
            )
    
    def get_statistics(self) -> Dict[str, int]:
        """Get counts of nodes and relationships."""
        with self.driver.session() as session:
            disease_count = session.run("MATCH (d:Disease) RETURN count(d) AS count").single()["count"]
            symptom_count = session.run("MATCH (s:Symptom) RETURN count(s) AS count").single()["count"]
            rel_count = session.run("MATCH ()-[r:HAS_SYMPTOM]->() RETURN count(r) AS count").single()["count"]
            
            return {
                "diseases": disease_count,
                "symptoms": symptom_count,
                "relationships": rel_count
            }


# ----------------------------
# MAIN PIPELINE
# ----------------------------

def main():
    print("=" * 60)
    print("SQL to Neo4j Knowledge Graph Pipeline")
    print("=" * 60)
    
    # 1. Connect to PostgreSQL
    print("\n[1/6] Connecting to PostgreSQL...")
    conn = get_connection()
    print("Connected to PostgreSQL")
    
    # 2. Fetch diseases data
    print("\n[2/6] Fetching diseases from PostgreSQL...")
    diseases_cols = [
        "name",
        "main_url",
        "description",
        "symptoms",
        "causes",
        "diagnosis",
        "prevention",
        "treatment",
        "living_with",
        "questions_to_ask",
        "resources",
    ]
    diseases_rows = fetch_all_rows(conn, "diseases", diseases_cols)
    print(f"Fetched {len(diseases_rows)} diseases")
    conn.close()
    
    # 3. Load spaCy NER model
    print("\n[3/6] Loading spaCy biomedical NER model...")
    nlp = load_ner_model()
    
    # 4. Connect to Neo4j
    print("\n[4/6] Connecting to Neo4j...")
    neo4j_conn = Neo4jConnection(NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD)
    neo4j_conn.verify_connection()
    
    # Create constraints for unique nodes
    print("\n[5/6] Creating database constraints...")
    neo4j_conn.create_constraints()
    
    # 5. Process each disease and extract entities
    print("\n[6/6] Processing diseases and extracting entities...")
    total_entities = 0
    
    for i, disease in enumerate(diseases_rows):
        disease_name = disease.get("name", "Unknown")
        description = disease.get("description", "")
        
        # Also include the symptoms field for more entity extraction
        symptoms_text = disease.get("symptoms", "")
        combined_text = f"{description} {symptoms_text}"
        
        # Create Disease node
        neo4j_conn.create_disease_node(disease)
        
        # Extract entities from description
        entities = extract_entities(nlp, combined_text)
        
        # Create Symptom nodes and relationships for DISEASE-type entities
        for entity_text, entity_label in entities:
            # Only use DISEASE entities as symptoms (the model tags symptoms as diseases)
            # Skip if the entity is the disease name itself
            if entity_text.lower() != disease_name.lower():
                neo4j_conn.create_symptom_node(entity_text, entity_label)
                neo4j_conn.create_has_symptom_relationship(disease_name, entity_text)
                total_entities += 1
        
        # Progress indicator
        if (i + 1) % 10 == 0 or i == len(diseases_rows) - 1:
            print(f"  Processed {i + 1}/{len(diseases_rows)} diseases...")
    
    # 6. Print statistics
    print("\n" + "=" * 60)
    print("Pipeline Complete!")
    print("=" * 60)
    
    stats = neo4j_conn.get_statistics()
    print(f"\nNeo4j Database Statistics:")
    print(f"  - Disease nodes: {stats['diseases']}")
    print(f"  - Symptom nodes: {stats['symptoms']}")
    print(f"  - HAS_SYMPTOM relationships: {stats['relationships']}")
    print(f"  - Total entities extracted: {total_entities}")
    
    neo4j_conn.close()
    print("\nDone! Your knowledge graph is ready in Neo4j.")


if __name__ == "__main__":
    main()
