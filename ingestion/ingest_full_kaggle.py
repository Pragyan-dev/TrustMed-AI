"""
Full Kaggle Dataset Ingestion to Neo4j Knowledge Graph

This script ingests four CSV files from the Kaggle medical dataset:
- dataset.csv: Disease-Symptom mappings (core structure)
- symptom_Description.csv: Disease descriptions
- Symptom-severity.csv: Symptom severity weights
- symptom_precaution.csv: Disease precautions

It creates a rich knowledge graph with:
- Disease nodes (with CUI, name, description)
- Symptom nodes (with CUI, name, severity)
- Precaution nodes (advice text)
- Relationships: HAS_SYMPTOM, HAS_PRECAUTION
"""

import pandas as pd
import os
import time
from dotenv import load_dotenv
from neo4j import GraphDatabase
from umls_client import UMLSClient

load_dotenv()

# Configuration
NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USERNAME = os.getenv("NEO4J_USERNAME", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD")
UMLS_API_KEY = os.getenv("UMLS_API_KEY")

# CSV file paths
DATA_DIR = "./archive 2"
DATASET_CSV = os.path.join(DATA_DIR, "dataset.csv")
DESCRIPTION_CSV = os.path.join(DATA_DIR, "symptom_Description.csv")
SEVERITY_CSV = os.path.join(DATA_DIR, "Symptom-severity.csv")
PRECAUTION_CSV = os.path.join(DATA_DIR, "symptom_precaution.csv")

# Rate limiting delay (seconds)
API_DELAY = 0.3


def clean_text(text):
    """Replace underscores with spaces and strip whitespace."""
    if pd.isna(text) or not text:
        return None
    return str(text).replace('_', ' ').strip()


class KaggleGraphIngester:
    """Handles ingestion of Kaggle medical data into Neo4j."""
    
    def __init__(self):
        self.driver = GraphDatabase.driver(
            NEO4J_URI,
            auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
        )
        self.umls = UMLSClient(api_key=UMLS_API_KEY)
        
        # Cache to avoid redundant UMLS lookups
        self.disease_cache = {}  # name -> (cui, umls_name)
        self.symptom_cache = {}  # name -> (cui, umls_name)
        
        # Stats
        self.stats = {
            'diseases_added': 0,
            'symptoms_added': 0,
            'relationships_added': 0,
            'descriptions_added': 0,
            'severities_added': 0,
            'precautions_added': 0
        }
    
    def close(self):
        self.driver.close()
    
    def _get_disease_cui(self, name):
        """Get disease CUI with caching."""
        if name in self.disease_cache:
            return self.disease_cache[name]
        
        result = self.umls.get_cui(name)
        self.disease_cache[name] = result
        time.sleep(API_DELAY)
        return result
    
    def _get_symptom_cui(self, name):
        """Get symptom CUI with caching."""
        if name in self.symptom_cache:
            return self.symptom_cache[name]
        
        result = self.umls.get_cui(name)
        self.symptom_cache[name] = result
        time.sleep(API_DELAY)
        return result
    
    # =========================================================================
    # PHASE 1: Core Structure (dataset.csv)
    # =========================================================================
    
    def phase1_core_structure(self):
        """Load dataset.csv and create Disease-Symptom relationships."""
        print("\n" + "=" * 60)
        print("PHASE 1: Core Structure (dataset.csv)")
        print("=" * 60)
        
        df = pd.read_csv(DATASET_CSV)
        total_rows = len(df)
        
        with self.driver.session() as session:
            for idx, row in df.iterrows():
                disease_name = clean_text(row['Disease'])
                if not disease_name:
                    continue
                
                print(f"\n[{idx + 1}/{total_rows}] Processing: {disease_name}")
                
                # Validate disease with UMLS
                disease_result = self._get_disease_cui(disease_name)
                if not disease_result:
                    print(f"  ⚠ Disease not found in UMLS, using name only")
                    disease_cui = None
                    disease_umls_name = disease_name
                else:
                    disease_cui, disease_umls_name = disease_result
                    print(f"  ✓ Disease CUI: {disease_cui}")
                
                # Merge disease node
                session.run("""
                    MERGE (d:Disease {name: $name})
                    SET d.cui = $cui,
                        d.umls_name = $umls_name,
                        d.last_updated = timestamp()
                """, name=disease_name, cui=disease_cui, umls_name=disease_umls_name)
                self.stats['diseases_added'] += 1
                
                # Process symptoms (Symptom_1 through Symptom_17)
                for i in range(1, 18):
                    col_name = f'Symptom_{i}'
                    if col_name not in row or pd.isna(row[col_name]):
                        continue
                    
                    symptom_name = clean_text(row[col_name])
                    if not symptom_name:
                        continue
                    
                    # Validate symptom with UMLS
                    symptom_result = self._get_symptom_cui(symptom_name)
                    if symptom_result:
                        symptom_cui, symptom_umls_name = symptom_result
                    else:
                        symptom_cui = None
                        symptom_umls_name = symptom_name
                    
                    # Merge symptom and relationship
                    session.run("""
                        MATCH (d:Disease {name: $disease_name})
                        MERGE (s:Symptom {name: $symptom_name})
                        SET s.cui = $symptom_cui,
                            s.umls_name = $symptom_umls_name
                        MERGE (d)-[:HAS_SYMPTOM]->(s)
                    """, 
                        disease_name=disease_name,
                        symptom_name=symptom_name,
                        symptom_cui=symptom_cui,
                        symptom_umls_name=symptom_umls_name
                    )
                    self.stats['symptoms_added'] += 1
                    self.stats['relationships_added'] += 1
        
        print(f"\n✓ Phase 1 complete: {self.stats['diseases_added']} diseases, {self.stats['symptoms_added']} symptoms")
    
    # =========================================================================
    # PHASE 2: Descriptions (symptom_Description.csv)
    # =========================================================================
    
    def phase2_descriptions(self):
        """Load symptom_Description.csv and add descriptions to diseases."""
        print("\n" + "=" * 60)
        print("PHASE 2: Disease Descriptions (symptom_Description.csv)")
        print("=" * 60)
        
        df = pd.read_csv(DESCRIPTION_CSV)
        
        with self.driver.session() as session:
            for idx, row in df.iterrows():
                disease_name = clean_text(row['Disease'])
                description = row.get('Description', '')
                
                if not disease_name or not description:
                    continue
                
                # Fuzzy match disease in Neo4j
                result = session.run("""
                    MATCH (d:Disease)
                    WHERE toLower(d.name) CONTAINS toLower($name)
                    SET d.description = $description
                    RETURN d.name
                """, name=disease_name, description=str(description))
                
                matched = list(result)
                if matched:
                    self.stats['descriptions_added'] += 1
                    print(f"  ✓ Added description for: {matched[0]['d.name']}")
                else:
                    print(f"  ⚠ No match for: {disease_name}")
        
        print(f"\n✓ Phase 2 complete: {self.stats['descriptions_added']} descriptions added")
    
    # =========================================================================
    # PHASE 3: Severity (Symptom-severity.csv)
    # =========================================================================
    
    def phase3_severity(self):
        """Load Symptom-severity.csv and add severity weights to symptoms."""
        print("\n" + "=" * 60)
        print("PHASE 3: Symptom Severity (Symptom-severity.csv)")
        print("=" * 60)
        
        df = pd.read_csv(SEVERITY_CSV)
        
        with self.driver.session() as session:
            for idx, row in df.iterrows():
                symptom_name = clean_text(row['Symptom'])
                weight = row.get('weight', 0)
                
                if not symptom_name:
                    continue
                
                # Match symptom in Neo4j (fuzzy match)
                result = session.run("""
                    MATCH (s:Symptom)
                    WHERE toLower(s.name) = toLower($name)
                    SET s.severity = toInteger($weight)
                    RETURN s.name
                """, name=symptom_name, weight=int(weight))
                
                matched = list(result)
                if matched:
                    self.stats['severities_added'] += 1
        
        print(f"\n✓ Phase 3 complete: {self.stats['severities_added']} severity weights added")
    
    # =========================================================================
    # PHASE 4: Precautions (symptom_precaution.csv)
    # =========================================================================
    
    def phase4_precautions(self):
        """Load symptom_precaution.csv and create Precaution nodes."""
        print("\n" + "=" * 60)
        print("PHASE 4: Precautions (symptom_precaution.csv)")
        print("=" * 60)
        
        df = pd.read_csv(PRECAUTION_CSV)
        
        with self.driver.session() as session:
            for idx, row in df.iterrows():
                disease_name = clean_text(row['Disease'])
                
                if not disease_name:
                    continue
                
                # Process Precaution_1 through Precaution_4
                for i in range(1, 5):
                    col_name = f'Precaution_{i}'
                    if col_name not in row or pd.isna(row[col_name]):
                        continue
                    
                    precaution_text = clean_text(row[col_name])
                    if not precaution_text:
                        continue
                    
                    # NOTE: Do NOT validate precautions with UMLS (they are phrases, not terms)
                    # Match disease and create precaution relationship
                    result = session.run("""
                        MATCH (d:Disease)
                        WHERE toLower(d.name) CONTAINS toLower($disease_name)
                        MERGE (p:Precaution {name: $precaution})
                        MERGE (d)-[:HAS_PRECAUTION]->(p)
                        RETURN d.name
                    """, disease_name=disease_name, precaution=precaution_text)
                    
                    if list(result):
                        self.stats['precautions_added'] += 1
        
        print(f"\n✓ Phase 4 complete: {self.stats['precautions_added']} precautions added")
    
    # =========================================================================
    # Summary
    # =========================================================================
    
    def print_summary(self):
        """Print final statistics."""
        print("\n" + "=" * 60)
        print("INGESTION COMPLETE - SUMMARY")
        print("=" * 60)
        print(f"  📊 Diseases added:     {self.stats['diseases_added']}")
        print(f"  📊 Symptoms added:     {self.stats['symptoms_added']}")
        print(f"  📊 Relationships:      {self.stats['relationships_added']}")
        print(f"  📊 Descriptions:       {self.stats['descriptions_added']}")
        print(f"  📊 Severity weights:   {self.stats['severities_added']}")
        print(f"  📊 Precautions:        {self.stats['precautions_added']}")
        print("=" * 60)


def ingest_all():
    """Main ingestion function."""
    print("\n" + "=" * 60)
    print("KAGGLE MEDICAL DATASET → NEO4J KNOWLEDGE GRAPH")
    print("=" * 60)
    
    ingester = KaggleGraphIngester()
    
    try:
        ingester.phase1_core_structure()
        ingester.phase2_descriptions()
        ingester.phase3_severity()
        ingester.phase4_precautions()
        ingester.print_summary()
    except Exception as e:
        print(f"\n❌ Error during ingestion: {e}")
        raise
    finally:
        ingester.close()


if __name__ == "__main__":
    ingest_all()
