"""
Quick test of Visual RAG on a test image.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.ingest_images import embed_image, load_model
import chromadb

# Test image from holdout set
TEST_IMAGE = "data/chest_xray/test/PNEUMONIA/person100_bacteria_475.jpeg"
GROUND_TRUTH = "PNEUMONIA"

print("=" * 60)
print("🧪 VISUAL RAG TEST - Holdout Image")
print("=" * 60)
print(f"\nTest Image: {TEST_IMAGE}")
print(f"Ground Truth: {GROUND_TRUTH}")

# Load model and embed test image
print("\n📦 Loading BiomedCLIP...")
load_model()

print("🔍 Generating embedding for test image...")
query_embedding = embed_image(TEST_IMAGE)

# Search in ChromaDB
print("🔎 Searching for similar images...")
client = chromadb.PersistentClient(path="./data/chroma_db")
collection = client.get_collection("medical_images")

results = collection.query(
    query_embeddings=[query_embedding],
    n_results=10
)

print("\n" + "=" * 60)
print("📊 TOP 10 SIMILAR IMAGES")
print("=" * 60)

label_counts = {"PNEUMONIA": 0, "NORMAL": 0, "OTHER": 0}

for i, (img_id, distance, metadata) in enumerate(zip(
    results['ids'][0], 
    results['distances'][0], 
    results['metadatas'][0]
)):
    similarity = (1 - distance) * 100
    label = metadata.get('label', metadata.get('modality', 'unknown'))
    
    # Count labels
    if label == "PNEUMONIA":
        label_counts["PNEUMONIA"] += 1
    elif label == "NORMAL":
        label_counts["NORMAL"] += 1
    else:
        label_counts["OTHER"] += 1
    
    print(f"{i+1}. {img_id[:40]:40s} | {similarity:5.1f}% | {label}")

print("\n" + "-" * 40)
print("LABEL DISTRIBUTION IN TOP 10:")
print(f"  • PNEUMONIA: {label_counts['PNEUMONIA']}")
print(f"  • NORMAL: {label_counts['NORMAL']}")
print(f"  • OTHER (ROCO): {label_counts['OTHER']}")

# Prediction based on majority
if label_counts['PNEUMONIA'] > label_counts['NORMAL']:
    prediction = "PNEUMONIA"
elif label_counts['NORMAL'] > label_counts['PNEUMONIA']:
    prediction = "NORMAL"
else:
    prediction = "UNCERTAIN"

print("\n" + "=" * 60)
print(f"🎯 PREDICTION: {prediction}")
print(f"✓ GROUND TRUTH: {GROUND_TRUTH}")
print(f"{'✅ CORRECT!' if prediction == GROUND_TRUTH else '❌ INCORRECT'}")
print("=" * 60)
