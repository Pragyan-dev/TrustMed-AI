"""
Ingest MIMIC-CXR-JPG Subset into ChromaDB

Reads the downloaded subset from data/mimic_cxr/ and ingests images
into ChromaDB using BiomedCLIP embeddings with multi-label metadata.

Usage:
    python ingestion/ingest_mimic_cxr.py
"""

import os
import sys
import csv
from pathlib import Path

# Add project root
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from ingestion.ingest_images import embed_image, load_model
from src.runtime_config import DATA_DIR as TRUSTMED_DATA_DIR, CHROMA_DB_DIR
import chromadb


# =============================================================================
# Configuration
# =============================================================================

DATA_DIR = Path(TRUSTMED_DATA_DIR) / "mimic_cxr"
IMAGES_DIR = DATA_DIR / "images"
LABELS_CSV = DATA_DIR / "subset_labels.csv"
COLLECTION_NAME = "medical_images"
BATCH_SIZE = 50  # Upsert in batches for efficiency


# =============================================================================
# Ingestion
# =============================================================================

def ingest_mimic_cxr():
    """
    Ingest MIMIC-CXR subset into ChromaDB with multi-label metadata.
    """
    print("=" * 60)
    print("🫁 Ingesting MIMIC-CXR-JPG Subset")
    print("=" * 60)

    # Validate files exist
    if not LABELS_CSV.exists():
        print(f"❌ Labels file not found: {LABELS_CSV}")
        print("   Run scripts/download_mimic_cxr_subset.py first.")
        sys.exit(1)

    # Load subset labels
    print(f"\n📖 Loading labels from {LABELS_CSV}...")
    records = []
    with open(LABELS_CSV, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            img_path = IMAGES_DIR / row["rel_path"]
            if img_path.exists():
                records.append(row)

    print(f"   Found {len(records)} images with labels")

    if not records:
        print("❌ No images found. Download images first.")
        sys.exit(1)

    # Pre-load BiomedCLIP
    print("\n📦 Loading BiomedCLIP model...")
    load_model()

    # Get ChromaDB collection
    client = chromadb.PersistentClient(path=CHROMA_DB_DIR)
    collection = client.get_or_create_collection(
        name=COLLECTION_NAME,
        metadata={"description": "Medical images with BiomedCLIP embeddings"}
    )

    existing_count = collection.count()
    print(f"📊 Existing images in collection: {existing_count}")

    # Batch ingestion
    total_ingested = 0
    total_skipped = 0
    total_errors = 0

    # Prepare batches
    batch_ids = []
    batch_embeddings = []
    batch_metadatas = []

    for i, row in enumerate(records):
        try:
            img_path = str(IMAGES_DIR / row["rel_path"])
            img_id = f"mimic_cxr_{row['dicom_id']}"

            # Check if already exists
            existing = collection.get(ids=[img_id])
            if existing and existing["ids"]:
                total_skipped += 1
                continue

            # Generate embedding
            embedding = embed_image(img_path)
            if embedding is None:
                total_errors += 1
                continue

            # Build multi-label metadata
            labels_str = row.get("labels", "No Finding")
            labels_list = [l.strip() for l in labels_str.split("|") if l.strip()]

            metadata = {
                "filename": os.path.basename(row["rel_path"]),
                "path": img_path,
                "source": "mimic-cxr-jpg",
                "modality": "chest-xray",
                "label": labels_str,                  # Full label string
                "labels_list": "|".join(labels_list),  # Pipe-separated for parsing
                "labels_count": str(len(labels_list)),
                "subject_id": row["subject_id"],
                "study_id": row["study_id"],
                "dicom_id": row["dicom_id"],
                "view_position": row.get("view_position", ""),
                "caption": f"Chest X-ray - {labels_str}",
            }

            batch_ids.append(img_id)
            batch_embeddings.append(embedding)
            batch_metadatas.append(metadata)

            # Flush batch
            if len(batch_ids) >= BATCH_SIZE:
                collection.upsert(
                    ids=batch_ids,
                    embeddings=batch_embeddings,
                    metadatas=batch_metadatas,
                )
                total_ingested += len(batch_ids)
                print(f"   ✓ Batch ingested: {total_ingested}/{len(records)} "
                      f"({total_skipped} skipped, {total_errors} errors)")
                batch_ids.clear()
                batch_embeddings.clear()
                batch_metadatas.clear()

        except Exception as e:
            total_errors += 1
            if (total_errors <= 5):
                print(f"   ✗ Error with {row.get('dicom_id', '?')}: {e}")

    # Flush remaining
    if batch_ids:
        collection.upsert(
            ids=batch_ids,
            embeddings=batch_embeddings,
            metadatas=batch_metadatas,
        )
        total_ingested += len(batch_ids)

    final_count = collection.count()
    print(f"\n{'=' * 60}")
    print(f"✅ MIMIC-CXR Ingestion Complete!")
    print(f"   • New images added: {total_ingested}")
    print(f"   • Skipped (already exist): {total_skipped}")
    print(f"   • Errors: {total_errors}")
    print(f"   • Total in collection: {final_count}")
    print(f"{'=' * 60}")

    # Label distribution
    print("\n📊 Ingested Label Distribution:")
    from collections import Counter
    label_counts = Counter()
    for row in records:
        for lbl in row.get("labels", "").split("|"):
            lbl = lbl.strip()
            if lbl:
                label_counts[lbl] += 1
    for lbl, cnt in label_counts.most_common():
        print(f"   {lbl:30s}: {cnt}")


if __name__ == "__main__":
    ingest_mimic_cxr()
