from src.trustmed_brain import get_graph_chain
import os
import sys

print("Initializing Graph Chain...")
try:
    chain = get_graph_chain()
    print("Executing query...")
    results = chain.graph.query("MATCH (n)-[r]->(m) WHERE toLower(n.name) CONTAINS 'atelect' RETURN n.name, type(r), m.name LIMIT 10")
    print(f"Graph Results: {results}")
    
    q_results = chain.graph.query("MATCH (n) WHERE toLower(n.name) CONTAINS 'pneumonia' RETURN n.name LIMIT 10")
    print(f"Pneumonia Results: {q_results}")
except Exception as e:
    print(f"Error: {e}")
