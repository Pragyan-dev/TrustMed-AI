#!/usr/bin/env python3
"""
Download a balanced subset of MIMIC-CXR-JPG from PhysioNet.

Uses a single wget -i batch call for maximum speed.

Prerequisites:  brew install wget

Usage:
    python scripts/download_mimic_cxr_subset.py --user YOUR_PHYSIONET_USERNAME
"""

import os
import sys
import csv
import argparse
import getpass
import subprocess
import tempfile
from pathlib import Path
from collections import defaultdict

# =============================================================================
# Configuration
# =============================================================================

BASE_URL = "https://physionet.org/files/mimic-cxr-jpg/2.1.0"
DATA_DIR = Path("data/mimic_cxr")
IMAGES_DIR = DATA_DIR / "images"
METADATA_DIR = DATA_DIR / "metadata"

CONDITIONS = [
    "Atelectasis", "Cardiomegaly", "Consolidation", "Edema",
    "Enlarged Cardiomediastinum", "Fracture", "Lung Lesion", "Lung Opacity",
    "No Finding", "Pleural Effusion", "Pleural Other", "Pneumonia",
    "Pneumothorax", "Support Devices",
]

IMAGES_PER_CONDITION = 150
MAX_TOTAL_IMAGES = 2500


# =============================================================================
# Helpers
# =============================================================================

def wget_single(url, dest, user, password):
    """Download one file via wget (for metadata CSVs)."""
    if dest.exists() and dest.stat().st_size > 0:
        print(f"  ✓ Already exists: {dest.name}")
        return True
    dest.parent.mkdir(parents=True, exist_ok=True)
    print(f"  ⬇ Downloading: {dest.name} ...")
    r = subprocess.run(
        ["wget", "-q", "--show-progress", "--user", user,
         "--password", password, "-O", str(dest), url],
        timeout=300)
    ok = r.returncode == 0 and dest.exists() and dest.stat().st_size > 0
    if ok:
        print(f"  ✅ {dest.name} ({dest.stat().st_size / 1024 / 1024:.1f} MB)")
    else:
        if dest.exists(): dest.unlink()
    return ok


def load_labels(path):
    import gzip
    labels = {}
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt") as f:
        for row in csv.DictReader(f):
            key = (row["subject_id"], row["study_id"])
            labels[key] = {c: row.get(c, "") for c in CONDITIONS}
    return labels


def load_metadata(path):
    import gzip
    records = []
    opener = gzip.open if str(path).endswith(".gz") else open
    with opener(path, "rt") as f:
        for row in csv.DictReader(f):
            s = f"p{row['subject_id']}"
            rel = f"{s[:3]}/{s}/s{row['study_id']}/{row['dicom_id']}.jpg"
            records.append({
                "subject_id": row["subject_id"],
                "study_id": row["study_id"],
                "dicom_id": row["dicom_id"],
                "ViewPosition": row.get("ViewPosition", ""),
                "rel_path": rel,
            })
    return records


def select_balanced_subset(labels, metadata, per_cond):
    print("\n📊 Selecting balanced subset...")
    meta_idx = defaultdict(list)
    for r in metadata:
        meta_idx[(r["subject_id"], r["study_id"])].append(r)

    cond_imgs = defaultdict(list)
    for (subj, study), cl in labels.items():
        for c in CONDITIONS:
            if cl.get(c) in ("1.0", "1"):
                recs = meta_idx.get((subj, study), [])
                pa = [r for r in recs if r["ViewPosition"] in ("PA", "AP")]
                if pa or recs:
                    cond_imgs[c].append((pa or recs)[0])

    selected = {}
    for c in CONDITIONS:
        imgs = cond_imgs[c]
        n = min(per_cond, len(imgs))
        print(f"  {c:30s}: {len(imgs):6d} avail → {n}")
        for r in imgs[:n]:
            selected[r["rel_path"]] = r
        if len(selected) >= MAX_TOTAL_IMAGES:
            break

    print(f"\n  Total unique images: {len(selected)}")
    return list(selected.values())


# =============================================================================
# Main
# =============================================================================

def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--user", required=True)
    parser.add_argument("--images-per-condition", type=int, default=IMAGES_PER_CONDITION)
    args = parser.parse_args()
    password = getpass.getpass(f"PhysioNet password for {args.user}: ")

    try:
        subprocess.run(["wget", "--version"], capture_output=True, timeout=5)
    except FileNotFoundError:
        print("❌ Install wget: brew install wget"); sys.exit(1)

    print("=" * 60)
    print("🫁 MIMIC-CXR-JPG Subset Downloader")
    print("=" * 60)

    METADATA_DIR.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    # Step 1: Metadata
    print("\n📋 Step 1: Metadata CSVs...")
    lp = METADATA_DIR / "mimic-cxr-2.0.0-chexpert.csv.gz"
    mp = METADATA_DIR / "mimic-cxr-2.0.0-metadata.csv.gz"
    for url, dest in [
        (f"{BASE_URL}/mimic-cxr-2.0.0-chexpert.csv.gz", lp),
        (f"{BASE_URL}/mimic-cxr-2.0.0-metadata.csv.gz", mp),
    ]:
        if not wget_single(url, dest, args.user, password):
            print(f"❌ Failed: {dest.name}"); sys.exit(1)

    # Step 2: Parse
    print("\n📖 Step 2: Parsing...")
    labels = load_labels(lp)
    print(f"  {len(labels)} studies")
    metadata = load_metadata(mp)
    print(f"  {len(metadata)} images")

    subset = select_balanced_subset(labels, metadata, args.images_per_condition)

    # Step 3: Filter out already-downloaded images
    to_download = []
    already_have = 0
    for rec in subset:
        dest = IMAGES_DIR / rec["rel_path"]
        if dest.exists() and dest.stat().st_size > 0:
            already_have += 1
        else:
            to_download.append(rec)

    if already_have > 0:
        print(f"\n  ✓ Already have {already_have} images, need {len(to_download)} more")

    # Step 4: Batch download with single wget -i call
    if to_download:
        print(f"\n⬇ Step 3: Batch downloading {len(to_download)} images (single wget call)...")

        # Write URL list file
        url_list = tempfile.NamedTemporaryFile(mode="w", suffix=".txt", delete=False)
        for rec in to_download:
            url_list.write(f"{BASE_URL}/files/{rec['rel_path']}\n")
        url_list.close()

        # Single wget call: -x creates directory structure, -nH removes hostname dir
        result = subprocess.run([
            "wget",
            "--user", args.user,
            "--password", password,
            "-i", url_list.name,        # Read URLs from file
            "-P", str(IMAGES_DIR),      # Save to images dir
            "-x",                       # Create directory structure
            "-nH",                      # No hostname directory
            "--cut-dirs=3",             # Remove /files/mimic-cxr-jpg/2.1.0 prefix
            "-q", "--show-progress",    # Quiet but show progress
            "-nc",                      # No clobber (skip existing)
        ])

        os.unlink(url_list.name)

        if result.returncode != 0:
            print(f"  ⚠ wget exited with code {result.returncode} (some files may have failed)")
    else:
        print("\n  ✓ All images already downloaded!")

    # Count results
    success = sum(1 for r in subset if (IMAGES_DIR / r["rel_path"]).exists())
    failures = len(subset) - success

    # Step 5: Save labels CSV
    print("\n💾 Step 4: Saving labels...")
    rows = []
    for rec in subset:
        key = (rec["subject_id"], rec["study_id"])
        cl = labels.get(key, {})
        pos = [c for c in CONDITIONS if cl.get(c) in ("1.0", "1")]
        rows.append({
            "subject_id": rec["subject_id"],
            "study_id": rec["study_id"],
            "dicom_id": rec["dicom_id"],
            "rel_path": rec["rel_path"],
            "view_position": rec.get("ViewPosition", ""),
            "labels": "|".join(pos) if pos else "No Finding",
            "labels_count": len(pos),
        })

    csv_path = DATA_DIR / "subset_labels.csv"
    with open(csv_path, "w", newline="") as f:
        w = csv.DictWriter(f, fieldnames=rows[0].keys())
        w.writeheader()
        w.writerows(rows)

    print(f"\n{'=' * 60}")
    print(f"✅ Done! {success} images downloaded, {failures} failures")
    print(f"   Labels: {csv_path}")
    print(f"   Images: {IMAGES_DIR}")
    print(f"{'=' * 60}")

    print("\n📊 Label Distribution:")
    dist = defaultdict(int)
    for r in rows:
        for l in r["labels"].split("|"):
            dist[l.strip()] += 1
    for l, c in sorted(dist.items(), key=lambda x: -x[1]):
        print(f"   {l:30s}: {c}")


if __name__ == "__main__":
    main()
