"""
Populate Neo4j Graph with Common Diseases from UMLS

This script ingests 50 common diseases into the Neo4j knowledge graph,
enriching each node with CUI identifiers and medical definitions from UMLS.
"""

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

# Dataset: 50 Common Diseases
COMMON_DISEASES = [
    'Hypertension',
    'Type 2 Diabetes',
    'Hyperlipidemia',
    'Coronary Artery Disease',
    'Asthma',
    'COPD',
    'Gastroesophageal Reflux Disease',
    'Osteoarthritis',
    'Depression',
    'Anxiety Disorder',
    'Hypothyroidism',
    'Chronic Kidney Disease',
    "Alzheimer's Disease",
    'Pneumonia',
    'Heart Failure',
    'Atrial Fibrillation',
    'Migraine',
    'Rheumatoid Arthritis',
    'Sleep Apnea',
    'Anemia',
    'Urinary Tract Infection',
    'Bronchitis',
    'Influenza',
    'COVID-19',
    'Dermatitis',
    'Psoriasis',
    'Acne',
    'Eczema',
    'Rosacea',
    'Gout',
    'Osteoporosis',
    'Fibromyalgia',
    'Multiple Sclerosis',
    "Parkinson's Disease",
    'Epilepsy',
    'Stroke',
    'Glaucoma',
    'Cataract',
    'Peptic Ulcer',
    "Crohn's Disease",
    'Ulcerative Colitis',
    'Irritable Bowel Syndrome',
    'Hepatitis B',
    'Hepatitis C',
    'Cirrhosis',
    'Kidney Stones',
    'Lupus',
    'Sepsis',
    'Tuberculosis',
    'Malaria'
]


def populate_graph():
    """
    Connect to Neo4j and populate with disease nodes from UMLS.
    """
    print("=" * 60)
    print("Neo4j Graph Population - Common Diseases")
    print("=" * 60)
    
    # Initialize connections
    driver = GraphDatabase.driver(
        NEO4J_URI,
        auth=(NEO4J_USERNAME, NEO4J_PASSWORD)
    )
    umls = UMLSClient(api_key=UMLS_API_KEY)
    
    total = len(COMMON_DISEASES)
    success_count = 0
    skip_count = 0
    
    try:
        with driver.session() as session:
            for idx, disease_name in enumerate(COMMON_DISEASES, 1):
                print(f"\nProcessing {idx}/{total}: {disease_name}...")
                
                # Get CUI from UMLS
                result = umls.get_cui(disease_name)
                
                if result:
                    cui, umls_name = result
                    print(f"  ✓ Found CUI: {cui} ({umls_name})")
                    
                    # Get definition
                    definitions = umls.get_definitions(cui)
                    description = definitions[0] if definitions else "No definition available."
                    
                    # Merge into Neo4j
                    session.run("""
                        MERGE (d:Disease {name: $name})
                        SET d.cui = $cui,
                            d.umls_name = $umls_name,
                            d.description = $description,
                            d.last_updated = timestamp()
                    """, 
                        name=disease_name,
                        cui=cui,
                        umls_name=umls_name,
                        description=description[:1000] if description else ""  # Truncate long descriptions
                    )
                    
                    success_count += 1
                    print(f"  ✓ Merged into Neo4j")
                else:
                    skip_count += 1
                    print(f"  ✗ Not found in UMLS, skipping")
                
                # Rate limiting - be polite to the API
                time.sleep(0.5)
                
    except Exception as e:
        print(f"\n❌ Error: {e}")
        raise
    finally:
        driver.close()
    
    # Summary
    print("\n" + "=" * 60)
    print("SUMMARY")
    print("=" * 60)
    print(f"✓ Successfully processed: {success_count}/{total}")
    print(f"✗ Skipped (not in UMLS): {skip_count}/{total}")
    print("=" * 60)


if __name__ == "__main__":
    populate_graph()
