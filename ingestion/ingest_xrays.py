"""
Ingest Labeled Chest X-Ray Dataset (Pneumonia vs Normal)

This script ingests the Kaggle Chest X-Ray dataset with labels,
enabling ground-truth Visual RAG results.
"""

import os
import sys
import random
from pathlib import Path

# Add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.ingest_images import embed_image, load_model
from src.runtime_config import DATA_DIR, CHROMA_DB_DIR
import chromadb


# =============================================================================
# Configuration
# =============================================================================

DATASET_DIR = os.path.join(DATA_DIR, "chest_xray", "train")
COLLECTION_NAME = "medical_images"
IMAGES_PER_CLASS = 500  # 500 NORMAL + 500 PNEUMONIA = 1000 total

# =============================================================================
# Ingestion
# =============================================================================

def ingest_labeled_xrays(dataset_dir: str, images_per_class: int = 500):
    """
    Ingest labeled chest X-rays with ground truth labels.
    
    Args:
        dataset_dir: Path to train/ folder with NORMAL and PNEUMONIA subdirs
        images_per_class: Number of images to ingest per class
    """
    print("=" * 60)
    print("🫁 Ingesting Labeled Chest X-Ray Dataset")
    print("=" * 60)
    
    # Pre-load model
    load_model()
    
    # Get ChromaDB collection
    client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "Medical images with BiomedCLIP embeddings"}
    )
    
    existing_count = collection.count()
    print(f"📊 Existing images in collection: {existing_count}")
    
    classes = ["NORMAL", "PNEUMONIA"]
    total_ingested = 0
    
    for label in classes:
        class_dir = Path(dataset_dir) / label
        if not class_dir.exists():
            print(f"⚠️ Directory not found: {class_dir}")
            continue
        
        # Get all images in class directory
        image_files = list(class_dir.glob("*.jpeg")) + list(class_dir.glob("*.jpg")) + list(class_dir.glob("*.png"))
        
        if len(image_files) == 0:
            print(f"⚠️ No images found in {class_dir}")
            continue
        
        # Randomly sample
        sample_size = min(images_per_class, len(image_files))
        sampled = random.sample(image_files, sample_size)
        
        print(f"\n📁 {label}: Ingesting {sample_size} of {len(image_files)} images...")
        
        for i, img_path in enumerate(sampled):
            try:
                # Create unique ID with label prefix
                img_id = f"xray_{label.lower()}_{img_path.stem}"
                
                # Check if already exists
                existing = collection.get(ids=[img_id])
                if existing and existing['ids']:
                    continue
                
                # Generate embedding
                embedding = embed_image(str(img_path))
                
                if embedding is None:
                    continue
                
                # Metadata with ground truth label
                metadata = {
                    "filename": img_path.name,
                    "label": label,  # Ground truth!
                    "modality": "chest-xray",
                    "source": "kaggle-pneumonia-dataset",
                    "caption": f"Chest X-ray - {label}"
                }
                
                # Add to collection
                collection.add(
                    embeddings=[embedding],
                    ids=[img_id],
                    metadatas=[metadata]
                )
                
                total_ingested += 1
                
                if (i + 1) % 50 == 0:
                    print(f"   ✓ {label}: {i+1}/{sample_size} ingested")
                    
            except Exception as e:
                print(f"   ✗ Error with {img_path.name}: {e}")
    
    final_count = collection.count()
    print(f"\n" + "=" * 60)
    print(f"✅ Ingestion Complete!")
    print(f"   • New images added: {total_ingested}")
    print(f"   • Total in collection: {final_count}")
    print("=" * 60)


if __name__ == "__main__":
    ingest_labeled_xrays(DATASET_DIR, IMAGES_PER_CLASS)
