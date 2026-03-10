#!/usr/bin/env python3
"""
Utility to generate subset_labels.csv for images that have already been downloaded.
This allows us to proceed with ingestion even if the full download is still running or was interrupted.
"""

import os
import sys
import csv
import gzip
from pathlib import Path
from collections import defaultdict

DATA_DIR = Path("data/mimic_cxr")
IMAGES_DIR = DATA_DIR / "images"
METADATA_DIR = DATA_DIR / "metadata"
LABEL_FILE = METADATA_DIR / "mimic-cxr-2.0.0-chexpert.csv.gz"
META_FILE = METADATA_DIR / "mimic-cxr-2.0.0-metadata.csv.gz"

CONDITIONS = [
    "Atelectasis", "Cardiomegaly", "Consolidation", "Edema",
    "Enlarged Cardiomediastinum", "Fracture", "Lung Lesion", "Lung Opacity",
    "No Finding", "Pleural Effusion", "Pleural Other", "Pneumonia",
    "Pneumothorax", "Support Devices",
]

def main():
    if not IMAGES_DIR.exists():
        print("❌ Images directory not found.")
        return

    print("🔍 Scanning images directory...")
    downloaded_paths = []
    for root, dirs, files in os.walk(IMAGES_DIR):
        for f in files:
            if f.endswith(".jpg"):
                full_path = Path(root) / f
                rel_path = full_path.relative_to(IMAGES_DIR)
                downloaded_paths.append(str(rel_path))

    print(f"📊 Found {len(downloaded_paths)} downloaded images.")

    if not LABEL_FILE.exists() or not META_FILE.exists():
        print("❌ Metadata CSVs not found in data/mimic_cxr/metadata/")
        return

    print("📖 Loading metadata/labels...")
    # Map dicom_id -> record
    metadata_map = {}
    with gzip.open(META_FILE, "rt") as f:
        reader = csv.DictReader(f)
        for row in reader:
            metadata_map[row["dicom_id"]] = row

    # Map (subject_id, study_id) -> labels
    labels_map = {}
    with gzip.open(LABEL_FILE, "rt") as f:
        reader = csv.DictReader(f)
        for row in reader:
            key = (row["subject_id"], row["study_id"])
            labels_map[key] = row

    print("💾 Generating subset_labels.csv...")
    subset_labels = []
    for rel_path in downloaded_paths:
        # Extract dicom_id from p10/p10000032/s50414267/02aa804e-bde0afdd-112c0b34-7bc16630-4e384014.jpg
        dicom_id = Path(rel_path).stem
        
        meta = metadata_map.get(dicom_id)
        if not meta:
            continue
            
        key = (meta["subject_id"], meta["study_id"])
        cond_labels = labels_map.get(key, {})
        
        positive_labels = [
            cond for cond in CONDITIONS
            if cond_labels.get(cond) in ("1.0", "1")
        ]
        
        subset_labels.append({
            "subject_id": meta["subject_id"],
            "study_id": meta["study_id"],
            "dicom_id": dicom_id,
            "rel_path": rel_path,
            "view_position": meta.get("ViewPosition", ""),
            "labels": "|".join(positive_labels) if positive_labels else "No Finding",
            "labels_count": len(positive_labels),
        })

    if not subset_labels:
        print("❌ Could not match any downloaded images to metadata.")
        return

    labels_csv = DATA_DIR / "subset_labels.csv"
    with open(labels_csv, "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=subset_labels[0].keys())
        writer.writeheader()
        writer.writerows(subset_labels)

    print(f"✅ Success! Created {labels_csv} with {len(subset_labels)} entries.")

if __name__ == "__main__":
    main()
