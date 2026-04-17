import os
import re
import chromadb
from dotenv import load_dotenv
from langchain_huggingface import HuggingFaceEmbeddings
from langchain_community.vectorstores import Chroma
from langchain_core.documents import Document

load_dotenv()

def parse_sql_docs(file_path):
    """
    Parse setup_health_db.sql for disease and medicine descriptions.
    """
    with open(file_path, 'r') as f:
        content = f.read()
    
    docs = []
    
    # 1. Extract Diseases
    disease_section = content.split("INSERT INTO diseases")[1].split(";")[0]
    disease_matches = re.findall(r"\(\s*'(.*?)',\s*'(.*?)',\s*'(.*?)',\s*'(.*?)'", disease_section, re.DOTALL)
    for name, url, desc, symptoms in disease_matches:
        text = f"Disease: {name}\nDescription: {desc}\nSymptoms: {symptoms}"
        docs.append(Document(page_content=text, metadata={"source": url, "name": name, "type": "disease"}))
        
    # 2. Extract Medicines
    med_section = content.split("INSERT INTO medicines")[1].split(";")[0]
    med_matches = re.findall(r"\(\s*'(.*?)',\s*'(.*?)',\s*'(.*?)',\s*'(.*?)'", med_section, re.DOTALL)
    for name, url, desc, usage in med_matches:
        text = f"Medicine: {name}\nDescription: {desc}\nUsage: {usage}"
        docs.append(Document(page_content=text, metadata={"source": url, "name": name, "type": "medicine"}))
        
    return docs

def build_vector_store(documents):
    print(f"🧠 Building Medical Vector Store from {len(documents)} documents...")
    
    persist_directory = "data/chroma_db"
    if not os.path.exists("data"):
        os.makedirs("data")
        
    # Initialize embeddings
    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    
    # Create Chroma vector store
    vectorstore = Chroma.from_documents(
        documents=documents,
        embedding=embeddings,
        persist_directory=persist_directory
    )
    
    print(f"✅ Success! Vector store saved to {persist_directory}")

if __name__ == "__main__":
    sql_path = "setup_health_db.sql"
    if not os.path.exists(sql_path):
        print(f"❌ Error: {sql_path} not found")
        exit(1)
        
    docs = parse_sql_docs(sql_path)
    if not docs:
        print("⚠️ No medical data found to index.")
    else:
        build_vector_store(docs)
