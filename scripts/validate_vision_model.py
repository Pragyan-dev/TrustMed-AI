#!/usr/bin/env python3
"""
MedGemma 27B Vision Model Validation Script
=============================================
Evaluates the vision model against MIMIC-CXR ground truth labels.

Metrics computed:
  - JSON parse rate: Can the model produce valid structured output?
  - Modality detection accuracy: Does it correctly identify X-Ray?
  - Finding detection (per-label): Sensitivity, specificity, F1 per pathology
  - Hallucination rate: Findings mentioned that don't match any ground truth label
  - Latency: Mean / P95 response time
  - Overall accuracy: Macro-averaged F1 across all pathologies

Usage:
  python3 scripts/validate_vision_model.py                    # 30 random samples
  python3 scripts/validate_vision_model.py --n 100            # 100 samples
  python3 scripts/validate_vision_model.py --use-openrouter   # test fallback models
"""

import argparse
import csv
import json
import os
import random
import re
import sys
import time
from collections import defaultdict
from pathlib import Path

# Add project root to path
PROJECT_ROOT = str(Path(__file__).resolve().parent.parent)
sys.path.insert(0, PROJECT_ROOT)

from dotenv import load_dotenv
load_dotenv(os.path.join(PROJECT_ROOT, ".env"))

# ── Config ────────────────────────────────────────────────────────────────────

LABELS_CSV = os.path.join(PROJECT_ROOT, "data/mimic_cxr/subset_labels.csv")
IMAGES_DIR = os.path.join(PROJECT_ROOT, "data/mimic_cxr/images")

# All 14 CheXpert pathology labels in our dataset
ALL_LABELS = [
    "Atelectasis", "Cardiomegaly", "Consolidation", "Edema",
    "Enlarged Cardiomediastinum", "Fracture", "Lung Lesion",
    "Lung Opacity", "No Finding", "Pleural Effusion", "Pleural Other",
    "Pneumonia", "Pneumothorax", "Support Devices",
]

# Map ground truth labels to keywords we look for in model output
LABEL_KEYWORDS = {
    "Atelectasis":                ["atelectasis", "collapse", "volume loss"],
    "Cardiomegaly":               ["cardiomegaly", "enlarged heart", "cardiac enlargement", "heart size"],
    "Consolidation":              ["consolidation", "airspace disease", "consolidative"],
    "Edema":                      ["edema", "pulmonary edema", "fluid overload", "vascular congestion"],
    "Enlarged Cardiomediastinum":  ["mediastin", "widened mediastinum", "enlarged cardiomediastinum"],
    "Fracture":                   ["fracture", "broken", "rib fracture"],
    "Lung Lesion":                ["lesion", "mass", "nodule", "tumor"],
    "Lung Opacity":               ["opacity", "opacit", "haziness", "infiltrate"],
    "No Finding":                 ["normal", "no acute", "unremarkable", "no significant", "no finding", "clear lung"],
    "Pleural Effusion":           ["pleural effusion", "effusion", "fluid in pleural"],
    "Pleural Other":              ["pleural", "thickening", "pleural abnormality"],
    "Pneumonia":                  ["pneumonia", "infection", "infectious"],
    "Pneumothorax":               ["pneumothorax", "collapsed lung", "air in pleural"],
    "Support Devices":            ["support device", "line", "tube", "catheter", "pacemaker", "wire", "device"],
}


# ── Load dataset ──────────────────────────────────────────────────────────────

def load_dataset():
    """Load MIMIC-CXR labels CSV and resolve image paths."""
    samples = []
    with open(LABELS_CSV, "r") as f:
        reader = csv.DictReader(f)
        for row in reader:
            rel_path = row["rel_path"]
            img_path = os.path.join(IMAGES_DIR, rel_path)
            if not os.path.exists(img_path):
                continue
            labels = [l.strip() for l in row["labels"].split("|") if l.strip()]
            samples.append({
                "image_path": img_path,
                "labels": labels,
                "subject_id": row["subject_id"],
                "dicom_id": row["dicom_id"],
                "view": row.get("view_position", ""),
            })
    return samples


# ── Model callers ─────────────────────────────────────────────────────────────

def call_medgemma(image_path: str, prompt: str) -> dict:
    """Call MedGemma via Vertex AI and return (raw_text, latency, error)."""
    from src.vision_tool import call_medgemma_vertex
    t0 = time.time()
    try:
        raw = call_medgemma_vertex(image_path, prompt)
        return {"raw": raw, "latency": time.time() - t0, "error": None}
    except Exception as e:
        return {"raw": "", "latency": time.time() - t0, "error": str(e)}


def call_openrouter(image_path: str, prompt: str) -> dict:
    """Call the fallback OpenRouter vision model."""
    from src.vision_tool import OPENROUTER_API_KEY, OPENROUTER_URL, VISION_MODELS, encode_image
    from src.ssl_bootstrap import get_ssl_cert_path
    import requests, time
    t0 = time.time()
    try:
        mime_type = 'image/jpeg' if image_path.lower().endswith(('.jpg', '.jpeg')) else 'image/png'
        base64_image = encode_image(image_path)
        payload = {
            "model": VISION_MODELS[0],
            "messages": [{"role": "user", "content": [{"type": "text", "text": prompt}, {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{base64_image}"}}] }],
            "temperature": 0.1, "max_tokens": 400
        }
        headers = {"Authorization": f"Bearer {OPENROUTER_API_KEY}", "Content-Type": "application/json"}
        response = requests.post(OPENROUTER_URL, headers=headers, json=payload, verify=get_ssl_cert_path() or True)
        response.raise_for_status()
        raw = response.json().get('choices', [{}])[0].get('message', {}).get('content', '')
        return {"raw": raw, "latency": time.time() - t0, "error": None}
    except Exception as e:
        return {"raw": "", "latency": time.time() - t0, "error": str(e)}


# ── Parse model output ────────────────────────────────────────────────────────

def parse_vision_output(raw_text: str) -> dict:
    """Try to parse structured JSON from model output."""
    cleaned = raw_text.strip()

    # Strip markdown fences
    if cleaned.startswith("```"):
        cleaned = re.sub(r'^```\w*\n?', '', cleaned)
        if '```' in cleaned:
            cleaned = cleaned[:cleaned.rfind('```')]

    try:
        return json.loads(cleaned.strip())
    except json.JSONDecodeError:
        # Try to find JSON object in the text
        match = re.search(r'\{[\s\S]*\}', cleaned)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                pass
    return None


def extract_mentioned_findings(parsed: dict) -> list:
    """Extract all finding text from the structured output."""
    findings = []
    for item in parsed.get("high_confidence_findings", []):
        if isinstance(item, dict):
            findings.append(item.get("finding", ""))
        elif isinstance(item, str):
            findings.append(item)
    for item in parsed.get("uncertain_findings", []):
        if isinstance(item, dict):
            findings.append(item.get("finding", ""))
        elif isinstance(item, str):
            findings.append(item)
    impression = parsed.get("overall_impression", "")
    if impression:
        findings.append(impression)
    return findings


def check_label_detected(label: str, findings_text: list) -> bool:
    """Check if a ground truth label was mentioned in model findings."""
    keywords = LABEL_KEYWORDS.get(label, [label.lower()])
    combined = " ".join(findings_text).lower()
    return any(kw in combined for kw in keywords)


# ── Evaluation ────────────────────────────────────────────────────────────────

def evaluate(samples: list, use_openrouter: bool = False):
    """Run evaluation on a list of samples."""

    from src.vision_tool import VISION_SYSTEM_PROMPT
    prompt = VISION_SYSTEM_PROMPT

    caller = call_openrouter if use_openrouter else call_medgemma
    model_name = "OpenRouter (fallback)" if use_openrouter else "MedGemma 27B (Vertex AI)"

    print(f"\n{'='*70}")
    print(f"  MedGemma Vision Model Validation")
    print(f"  Model: {model_name}")
    print(f"  Samples: {len(samples)}")
    print(f"{'='*70}\n")

    # Accumulators
    results = []
    json_parse_ok = 0
    modality_correct = 0
    latencies = []
    errors = []

    # Per-label: TP, FP, FN
    label_tp = defaultdict(int)
    label_fp = defaultdict(int)
    label_fn = defaultdict(int)
    label_tn = defaultdict(int)
    hallucination_count = 0
    total_findings = 0

    for i, sample in enumerate(samples):
        img = sample["image_path"]
        gt_labels = set(sample["labels"])
        short_path = os.path.basename(img)

        print(f"[{i+1}/{len(samples)}] {short_path}  GT: {', '.join(gt_labels)}")

        # Call model
        result = caller(img, prompt)
        latencies.append(result["latency"])

        if result["error"]:
            errors.append({"image": short_path, "error": result["error"]})
            print(f"  ERROR: {result['error'][:80]}")
            results.append({"image": short_path, "status": "error", "error": result["error"]})
            # Count all GT labels as FN
            for label in gt_labels:
                label_fn[label] += 1
            continue

        # Parse JSON
        parsed = parse_vision_output(result["raw"])
        if parsed:
            json_parse_ok += 1
        else:
            print(f"  WARN: Failed to parse JSON")
            results.append({"image": short_path, "status": "parse_fail", "raw": result["raw"][:200]})
            for label in gt_labels:
                label_fn[label] += 1
            continue

        # Check modality
        modality = parsed.get("modality", "").strip()
        if modality.lower() in ["x-ray", "xray", "x ray"]:
            modality_correct += 1

        # Extract findings
        findings_text = extract_mentioned_findings(parsed)
        total_findings += len(parsed.get("high_confidence_findings", []))
        total_findings += len(parsed.get("uncertain_findings", []))

        # Per-label evaluation
        detected_any_gt = set()
        for label in ALL_LABELS:
            detected = check_label_detected(label, findings_text)
            is_present = label in gt_labels

            if detected and is_present:
                label_tp[label] += 1
                detected_any_gt.add(label)
            elif detected and not is_present:
                label_fp[label] += 1
            elif not detected and is_present:
                label_fn[label] += 1
            else:
                label_tn[label] += 1

        # Hallucination check: findings that match NO ground truth label
        for finding_str in findings_text:
            matched_any = False
            for label in gt_labels:
                keywords = LABEL_KEYWORDS.get(label, [label.lower()])
                if any(kw in finding_str.lower() for kw in keywords):
                    matched_any = True
                    break
            if not matched_any and finding_str.strip():
                hallucination_count += 1

        latency_ms = result["latency"] * 1000
        detected_labels = [l for l in ALL_LABELS if check_label_detected(l, findings_text)]
        print(f"  Detected: {', '.join(detected_labels) or 'none'}  ({latency_ms:.0f}ms)")

        results.append({
            "image": short_path,
            "status": "ok",
            "gt_labels": list(gt_labels),
            "detected_labels": detected_labels,
            "modality": modality,
            "latency_ms": latency_ms,
        })

    # ── Compute metrics ───────────────────────────────────────────────────────

    n = len(samples)
    n_ok = n - len(errors)

    print(f"\n{'='*70}")
    print(f"  RESULTS SUMMARY")
    print(f"{'='*70}\n")

    # Basic metrics
    print(f"  Samples evaluated:     {n}")
    print(f"  Successful calls:      {n_ok} ({100*n_ok/n:.1f}%)")
    print(f"  JSON parse rate:       {json_parse_ok}/{n_ok} ({100*json_parse_ok/max(n_ok,1):.1f}%)")
    print(f"  Modality correct:      {modality_correct}/{json_parse_ok} ({100*modality_correct/max(json_parse_ok,1):.1f}%)")
    print(f"  API errors:            {len(errors)}")

    # Latency
    if latencies:
        latencies_ms = [l * 1000 for l in latencies]
        latencies_ms.sort()
        p95_idx = int(0.95 * len(latencies_ms))
        print(f"\n  Latency:")
        print(f"    Mean:   {sum(latencies_ms)/len(latencies_ms):.0f} ms")
        print(f"    Median: {latencies_ms[len(latencies_ms)//2]:.0f} ms")
        print(f"    P95:    {latencies_ms[min(p95_idx, len(latencies_ms)-1)]:.0f} ms")
        print(f"    Min:    {min(latencies_ms):.0f} ms")
        print(f"    Max:    {max(latencies_ms):.0f} ms")

    # Per-label metrics
    print(f"\n  {'─'*68}")
    print(f"  {'Label':<30} {'Sens':>6} {'Spec':>6} {'Prec':>6} {'F1':>6}  {'TP':>4} {'FP':>4} {'FN':>4}")
    print(f"  {'─'*68}")

    f1_scores = []
    for label in ALL_LABELS:
        tp = label_tp[label]
        fp = label_fp[label]
        fn = label_fn[label]
        tn = label_tn[label]

        sensitivity = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        specificity = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        f1 = 2 * precision * sensitivity / (precision + sensitivity) if (precision + sensitivity) > 0 else 0.0
        f1_scores.append(f1)

        print(f"  {label:<30} {sensitivity:>6.1%} {specificity:>6.1%} {precision:>6.1%} {f1:>6.1%}  {tp:>4} {fp:>4} {fn:>4}")

    macro_f1 = sum(f1_scores) / len(f1_scores) if f1_scores else 0
    print(f"  {'─'*68}")
    print(f"  {'MACRO AVERAGE':<30} {'':>6} {'':>6} {'':>6} {macro_f1:>6.1%}")

    # Hallucination rate
    halluc_rate = hallucination_count / max(total_findings, 1)
    print(f"\n  Hallucination rate:    {hallucination_count}/{total_findings} findings ({100*halluc_rate:.1f}%)")
    print(f"  (Findings that matched no ground truth label)")

    # ── Save results ──────────────────────────────────────────────────────────

    output = {
        "model": model_name,
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "num_samples": n,
        "metrics": {
            "json_parse_rate": json_parse_ok / max(n_ok, 1),
            "modality_accuracy": modality_correct / max(json_parse_ok, 1),
            "macro_f1": macro_f1,
            "hallucination_rate": halluc_rate,
            "mean_latency_ms": sum(latencies) * 1000 / max(len(latencies), 1),
            "api_error_rate": len(errors) / n,
        },
        "per_label": {},
        "per_sample": results,
        "errors": errors,
    }

    for label in ALL_LABELS:
        tp = label_tp[label]
        fp = label_fp[label]
        fn = label_fn[label]
        tn = label_tn[label]
        sens = tp / (tp + fn) if (tp + fn) > 0 else 0
        prec = tp / (tp + fp) if (tp + fp) > 0 else 0
        f1 = 2 * prec * sens / (prec + sens) if (prec + sens) > 0 else 0
        output["per_label"][label] = {
            "sensitivity": round(sens, 4),
            "precision": round(prec, 4),
            "f1": round(f1, 4),
            "tp": tp, "fp": fp, "fn": fn, "tn": tn,
        }

    results_dir = os.path.join(PROJECT_ROOT, "results")
    os.makedirs(results_dir, exist_ok=True)
    out_file = os.path.join(results_dir, f"vision_validation_{time.strftime('%Y%m%d_%H%M%S')}.json")
    with open(out_file, "w") as f:
        json.dump(output, f, indent=2)

    print(f"\n  Results saved to: {out_file}")
    print(f"{'='*70}\n")

    return output


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Validate MedGemma vision model")
    parser.add_argument("--n", type=int, default=30, help="Number of samples to evaluate (default: 30)")
    parser.add_argument("--seed", type=int, default=42, help="Random seed for reproducibility")
    parser.add_argument("--use-openrouter", action="store_true", help="Test OpenRouter fallback model instead")
    parser.add_argument("--stratified", action="store_true", help="Stratified sampling (2-3 per label)")
    args = parser.parse_args()

    print("Loading MIMIC-CXR dataset...")
    all_samples = load_dataset()
    print(f"Found {len(all_samples)} images with labels.")

    if not all_samples:
        print("ERROR: No valid image-label pairs found. Check paths.")
        sys.exit(1)

    random.seed(args.seed)

    if args.stratified:
        # Pick 2-3 samples per label for balanced evaluation
        by_label = defaultdict(list)
        for s in all_samples:
            for l in s["labels"]:
                by_label[l].append(s)
        selected = set()
        per_label = max(2, args.n // len(ALL_LABELS))
        for label in ALL_LABELS:
            candidates = by_label.get(label, [])
            random.shuffle(candidates)
            for s in candidates[:per_label]:
                selected.add(s["dicom_id"])
        samples = [s for s in all_samples if s["dicom_id"] in selected]
        random.shuffle(samples)
        samples = samples[:args.n]
    else:
        samples = random.sample(all_samples, min(args.n, len(all_samples)))

    print(f"Selected {len(samples)} samples for evaluation.")
    evaluate(samples, use_openrouter=args.use_openrouter)


if __name__ == "__main__":
    main()
