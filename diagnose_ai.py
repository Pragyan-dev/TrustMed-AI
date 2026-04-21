
import os
import sys
import chromadb
from sentence_transformers import SentenceTransformer

# Absolute path for diagnostic
path = "/Users/chandanapulikanti/Downloads/TrustMed-AI/data/chroma_db"

print("--- TRUSTMED AI DIAGNOSTIC START ---")
print(f"1. Checking path: {path}")
if not os.path.exists(path):
    print("   ❌ ERROR: Database folder not found!")
    sys.exit(1)
print("   ✅ Path exists.")

print("\n2. Initializing ChromaDB Client...")
try:
    client = chromadb.PersistentClient(path=path)
    cols = client.list_collections()
    print(f"   ✅ Client connected. Found {len(cols)} collections: {[c.name for c in cols]}")
except Exception as e:
    print(f"   ❌ ERROR: Failed to connect to Chroma: {e}")
    sys.exit(1)

print("\n3. Testing Embedding Model (all-MiniLM-L6-v2)...")
try:
    model = SentenceTransformer('all-MiniLM-L6-v2')
    vec = model.encode(["test query"])
    print(f"   ✅ Model loaded. Embedding success (Shape: {vec.shape})")
except Exception as e:
    print(f"   ❌ ERROR: Model failed to load: {e}")
    sys.exit(1)

print("\n4. Testing Direct Retrieval...")
for c in cols:
    if c.name in ['diseases', 'symptoms', 'medicines']:
        try:
            res = c.query(query_embeddings=[vec.tolist()], n_results=1)
            count = len(res['documents'][0])
            print(f"   ✅ Collection '{c.name}': Successfully retrieved {count} document(s).")
            if count > 0:
                print(f"      Sample Data: {res['documents'][0][0][:60]}...")
        except Exception as e:
            print(f"   ❌ ERROR: Failed to query {c.name}: {e}")

print("\n--- DIAGNOSTIC COMPLETE ---")
