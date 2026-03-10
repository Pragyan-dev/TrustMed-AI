import chromadb
import os

# Point this to the folder you just replaced
CHROMA_DB_DIR = "./chroma_db" 

def verify_db():
    if not os.path.exists(CHROMA_DB_DIR):
        print(f"❌ Error: Folder '{CHROMA_DB_DIR}' not found!")
        return

    print(f"Checking database at: {CHROMA_DB_DIR}")
    
    try:
        client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
        collections = client.list_collections()
        
        print(f"✅ Connection Successful!")
        print(f"📂 Found {len(collections)} collections:")
        
        total_docs = 0
        for col in collections:
            count = col.count()
            total_docs += count
            print(f"   - Collection: '{col.name}' | Documents: {count}")
            
            # Sanity check: Peek at one item to ensure embeddings exist
            if count > 0:
                peek = col.peek(limit=1)
                if peek.get('embeddings') is not None and len(peek['embeddings']) > 0:
                    print(f"     (Embeddings detected ✓)")
                else:
                    print(f"     (⚠️ No embeddings found in peek!)")
        
        print(f"\nTotal Documents Available: {total_docs}")
        
    except Exception as e:
        print(f"❌ Failed to load database: {e}")

if __name__ == "__main__":
    verify_db()
