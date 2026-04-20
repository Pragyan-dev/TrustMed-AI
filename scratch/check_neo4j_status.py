import os
from neo4j import GraphDatabase
from dotenv import load_dotenv

load_dotenv()

NEO4J_URI = os.environ.get("NEO4J_URI")
NEO4J_USER = os.environ.get("NEO4J_USERNAME")
NEO4J_PASSWORD = os.environ.get("NEO4J_PASSWORD")

def check_status():
    if not all([NEO4J_URI, NEO4J_USER, NEO4J_PASSWORD]):
        print("Missing Neo4j credentials in environment.")
        return

    driver = GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, NEO4J_PASSWORD))
    try:
        with driver.session() as session:
            # Check total nodes
            res = session.run("MATCH (n) RETURN count(n) as cnt")
            print(f"Total nodes: {res.single()['cnt']}")

            # Check Patient nodes
            res = session.run("MATCH (p:Patient) RETURN count(p) as cnt")
            print(f"Patient nodes: {res.single()['cnt']}")

            # Check Disease nodes
            res = session.run("MATCH (d:Disease) RETURN count(d) as cnt")
            print(f"Disease nodes: {res.single()['cnt']}")

            # Check Drug nodes
            res = session.run("MATCH (dr:Drug) RETURN count(dr) as cnt")
            print(f"Drug nodes: {res.single()['cnt']}")

            # Check relationships
            res = session.run("MATCH ()-[r]->() RETURN type(r) as type, count(r) as cnt")
            print("\nRelationships by type:")
            for rec in res:
                print(f"  {rec['type']}: {rec['cnt']}")

    except Exception as e:
        print(f"Error connecting to Neo4j: {e}")
    finally:
        driver.close()

if __name__ == "__main__":
    check_status()
