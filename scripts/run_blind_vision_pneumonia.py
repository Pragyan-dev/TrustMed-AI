#!/usr/bin/env python3
"""
Run a pneumonia-focused blind vision benchmark with MedGemma.

The model receives only the image and a generic blind interpretation prompt.
Ground-truth labels/captions are used only after inference for scoring.
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import os
import random
import re
import subprocess
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path
from typing import Any

import requests
from dotenv import load_dotenv


REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

load_dotenv(REPO_ROOT / ".env")
os.environ["VISION_PROVIDER"] = "vertex"

LABELS_CSV = REPO_ROOT / "data" / "mimic_cxr" / "subset_labels.csv"
IMAGES_DIR = REPO_ROOT / "data" / "mimic_cxr" / "images"
PRIMARY_IMAGE = (
    "files/p10/p10001884/s50807032/"
    "ebf48d65-7e780cd5-59118fba-50977097-3720cc7e.jpg"
)

BLIND_PROMPT = (
    "Interpret this scan blindly and detail any pathological findings.\n\n"
    "You are a radiologist assistant. Do not assume patient history. "
    "Return ONLY valid JSON with this schema:\n"
    "{\n"
    '  "modality": "<X-Ray|CT|MRI|Ultrasound|Skin Photo|Pathology Slide|Unknown>",\n'
    '  "body_region": "<anatomical region visible>",\n'
    '  "high_confidence_findings": [\n'
    '    {"finding": "<visible finding>", "confidence": "HIGH"}\n'
    "  ],\n"
    '  "uncertain_findings": [\n'
    '    {"finding": "<uncertain finding>", "confidence": "LOW"}\n'
    "  ],\n"
    '  "cannot_assess": ["<limitations>"],\n'
    '  "overall_impression": "<1-2 sentence conservative summary>"\n'
    "}\n"
    "Only include findings visible on the image. Put uncertainty in "
    "uncertain_findings rather than overstating a diagnosis."
)

ALL_LABELS = [
    "Atelectasis",
    "Cardiomegaly",
    "Consolidation",
    "Edema",
    "Enlarged Cardiomediastinum",
    "Fracture",
    "Lung Lesion",
    "Lung Opacity",
    "No Finding",
    "Pleural Effusion",
    "Pleural Other",
    "Pneumonia",
    "Pneumothorax",
    "Support Devices",
]

LABEL_KEYWORDS = {
    "Atelectasis": ["atelectasis", "collapse", "volume loss"],
    "Cardiomegaly": ["cardiomegaly", "enlarged heart", "cardiac enlargement"],
    "Consolidation": ["consolidation", "airspace disease", "consolidative"],
    "Edema": ["edema", "pulmonary edema", "fluid overload", "vascular congestion"],
    "Enlarged Cardiomediastinum": ["mediastin", "widened mediastinum", "cardiomediastinum"],
    "Fracture": ["fracture", "broken", "rib fracture"],
    "Lung Lesion": ["lesion", "mass", "nodule", "tumor"],
    "Lung Opacity": ["opacity", "opacit", "haziness", "infiltrate", "infiltration"],
    "No Finding": ["normal", "no acute", "unremarkable", "no significant", "clear lung"],
    "Pleural Effusion": ["pleural effusion", "effusion", "pleural fluid"],
    "Pleural Other": ["pleural thickening", "pleural abnormality", "pleural other"],
    "Pneumonia": ["pneumonia", "infection", "infectious", "pneumonic"],
    "Pneumothorax": ["pneumothorax", "collapsed lung", "pleural air"],
    "Support Devices": ["support device", "line", "tube", "catheter", "pacemaker", "wire", "device"],
}

CAPTION_STOPWORDS = {"chest", "x", "ray", "xray", "and", "or", "the", "of", "with"}


def load_samples() -> list[dict[str, Any]]:
    samples = []
    with LABELS_CSV.open() as f:
        for row in csv.DictReader(f):
            labels = [label.strip() for label in row["labels"].split("|") if label.strip()]
            image_path = IMAGES_DIR / row["rel_path"]
            if "Pneumonia" not in labels or not image_path.exists():
                continue
            caption = f"Chest X-ray - {row['labels']}"
            samples.append(
                {
                    "subject_id": row["subject_id"],
                    "study_id": row["study_id"],
                    "dicom_id": row["dicom_id"],
                    "rel_path": row["rel_path"],
                    "image_path": str(image_path),
                    "view_position": row.get("view_position", ""),
                    "true_labels": labels,
                    "baseline_caption": caption,
                }
            )
    return samples


def select_pneumonia_cohort(samples: list[dict[str, Any]], n: int, seed: int) -> list[dict[str, Any]]:
    by_rel_path = {sample["rel_path"]: sample for sample in samples}
    if PRIMARY_IMAGE not in by_rel_path:
        raise RuntimeError(f"Primary pneumonia image not found in {LABELS_CSV}: {PRIMARY_IMAGE}")

    primary = by_rel_path[PRIMARY_IMAGE]
    rng = random.Random(seed)

    def group(priority_fn):
        matches = [sample for sample in samples if sample["rel_path"] != PRIMARY_IMAGE and priority_fn(sample)]
        rng.shuffle(matches)
        return matches

    ordered = [primary]
    ordered.extend(group(lambda s: s["true_labels"] == ["Pneumonia"] and s["view_position"] in {"PA", "AP"}))
    ordered.extend(group(lambda s: s["true_labels"] == ["Pneumonia"]))
    ordered.extend(group(lambda s: s["view_position"] in {"PA", "AP"}))
    ordered.extend(group(lambda s: True))

    selected = []
    seen = set()
    for sample in ordered:
        if sample["dicom_id"] in seen:
            continue
        selected.append(sample)
        seen.add(sample["dicom_id"])
        if len(selected) >= n:
            break
    return selected


def parse_json(raw_text: str) -> dict[str, Any] | None:
    cleaned = raw_text.strip()
    if cleaned.startswith("```"):
        cleaned = re.sub(r"^```\w*\n?", "", cleaned)
        if "```" in cleaned:
            cleaned = cleaned[: cleaned.rfind("```")]
    try:
        return json.loads(cleaned)
    except json.JSONDecodeError:
        match = re.search(r"\{[\s\S]*\}", cleaned)
        if match:
            try:
                return json.loads(match.group())
            except json.JSONDecodeError:
                return None
    return None


def finding_text(parsed: dict[str, Any] | None, raw: str) -> str:
    if not parsed:
        return raw
    parts = []
    for key in ("high_confidence_findings", "uncertain_findings"):
        for item in parsed.get(key, []) or []:
            if isinstance(item, dict):
                parts.append(str(item.get("finding", "")))
            else:
                parts.append(str(item))
    parts.append(str(parsed.get("overall_impression", "")))
    parts.append(str(parsed.get("body_region", "")))
    return " ".join(part for part in parts if part).strip()


def detected_labels(text: str) -> list[str]:
    lowered = text.lower()
    detected = []
    for label in ALL_LABELS:
        if any(keyword in lowered for keyword in LABEL_KEYWORDS[label]):
            detected.append(label)
    if "No Finding" in detected and len(detected) > 1:
        detected.remove("No Finding")
    return detected


def tokenize(text: str) -> set[str]:
    return {
        token
        for token in re.findall(r"[a-z0-9]+", text.lower())
        if len(token) > 1 and token not in CAPTION_STOPWORDS
    }


def caption_overlap(caption: str, text: str) -> dict[str, Any]:
    caption_tokens = tokenize(caption)
    output_tokens = tokenize(text)
    overlap = sorted(caption_tokens & output_tokens)
    return {
        "caption_tokens": sorted(caption_tokens),
        "matched_tokens": overlap,
        "recall": round(len(overlap) / max(len(caption_tokens), 1), 4),
        "jaccard": round(len(overlap) / max(len(caption_tokens | output_tokens), 1), 4),
    }


def deterministic_judge(true_labels: list[str], predicted_labels: list[str], parsed_ok: bool) -> dict[str, Any]:
    true_set = set(true_labels)
    pred_set = set(predicted_labels)
    tp = len(true_set & pred_set)
    fp = len(pred_set - true_set)
    fn = len(true_set - pred_set)

    faithfulness = max(0, 10 - 2 * fp)
    completeness = max(0, 10 - 2 * fn)
    safety = 10 if fp == 0 else max(4, 10 - 2 * fp)
    calibration = 10 if parsed_ok else 7
    if "Pneumonia" not in pred_set:
        completeness = min(completeness, 6)
    if "Pneumonia" in pred_set and "Pneumonia" not in true_set:
        faithfulness = min(faithfulness, 4)

    score = round((faithfulness + completeness + safety + calibration) / 4)
    return {
        "score": int(score),
        "axes": {
            "faithfulness": faithfulness,
            "completeness": completeness,
            "safety": safety,
            "calibration": calibration,
        },
        "reasoning": (
            f"Deterministic Gemma-style rubric: TP={tp}, FP={fp}, FN={fn}, "
            f"pneumonia_detected={'Pneumonia' in pred_set}."
        ),
        "source": "deterministic_gemma_style_rubric",
    }


def llm_judge(raw_output: str, sample: dict[str, Any], predicted: list[str], fallback: dict[str, Any]) -> dict[str, Any]:
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        return fallback

    prompt = f"""
You are an independent Gemma-style medical imaging judge. Score the AI output
from 0 to 10 against the hidden ground truth. Do not reward unsupported claims.

Ground truth caption: {sample['baseline_caption']}
Ground truth labels: {', '.join(sample['true_labels'])}
Detected label keywords from output: {', '.join(predicted) or 'none'}

AI output:
{raw_output[:5000]}

Return only JSON:
{{
  "score": <integer 0-10>,
  "axes": {{
    "faithfulness": <0-10>,
    "completeness": <0-10>,
    "safety": <0-10>,
    "calibration": <0-10>
  }},
  "reasoning": "<one concise explanation>"
}}
""".strip()

    try:
        response = requests.post(
            "https://openrouter.ai/api/v1/chat/completions",
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "HTTP-Referer": "https://trustmed-ai.local",
                "X-Title": "TrustMed Blind Vision Judge",
            },
            json={
                "model": os.getenv("BLIND_VISION_JUDGE_MODEL", "google/gemma-3-4b-it:free"),
                "messages": [{"role": "user", "content": prompt}],
                "temperature": 0.0,
                "max_tokens": 350,
            },
            timeout=45,
        )
        if response.status_code != 200:
            raise RuntimeError(f"judge HTTP {response.status_code}: {response.text[:200]}")
        content = response.json()["choices"][0]["message"]["content"]
        parsed = parse_json(content)
        if not parsed:
            raise RuntimeError(f"judge returned non-JSON: {content[:200]}")
        score = max(0, min(10, int(round(float(parsed.get("score", fallback["score"]))))))
        axes = parsed.get("axes") if isinstance(parsed.get("axes"), dict) else fallback["axes"]
        return {
            "score": score,
            "axes": axes,
            "reasoning": str(parsed.get("reasoning", "")).strip() or fallback["reasoning"],
            "source": os.getenv("BLIND_VISION_JUDGE_MODEL", "google/gemma-3-4b-it:free"),
        }
    except Exception as exc:
        judged = dict(fallback)
        judged["source"] = f"{fallback['source']} (llm_judge_failed: {exc})"
        return judged


def call_medgemma(image_path: str) -> dict[str, Any]:
    from src.vision_tool import call_medgemma_vertex

    started = time.time()
    try:
        raw = call_medgemma_vertex(image_path, BLIND_PROMPT)
        return {
            "ok": True,
            "raw": raw,
            "latency_ms": round((time.time() - started) * 1000, 2),
            "error": None,
            "auth_source": "application_default_credentials",
        }
    except Exception as exc:
        adc_error = str(exc)
        try:
            raw = call_medgemma_with_gcloud_token(image_path)
            return {
                "ok": True,
                "raw": raw,
                "latency_ms": round((time.time() - started) * 1000, 2),
                "error": None,
                "auth_source": f"gcloud_user_token_after_adc_error: {adc_error[:180]}",
            }
        except Exception as fallback_exc:
            return {
                "ok": False,
                "raw": "",
                "latency_ms": round((time.time() - started) * 1000, 2),
                "error": f"ADC failed: {adc_error}; gcloud fallback failed: {fallback_exc}",
                "auth_source": "none",
            }


def call_medgemma_with_gcloud_token(image_path: str) -> str:
    project = os.getenv("VERTEX_PROJECT_ID", "")
    endpoint = os.getenv("VERTEX_ENDPOINT_ID", "")
    region = os.getenv("VERTEX_REGION", "us-central1")
    domain = os.getenv("VERTEX_DEDICATED_DOMAIN", "")
    if not project or not endpoint or not domain:
        raise RuntimeError("Vertex endpoint environment variables are not fully configured.")

    token = subprocess.check_output(["gcloud", "auth", "print-access-token"], text=True).strip()
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")
    ext = os.path.splitext(image_path)[1].lower()
    mime_type = "image/jpeg" if ext in {".jpg", ".jpeg"} else "image/png"

    url = (
        f"https://{domain}/v1beta1/projects/{project}"
        f"/locations/{region}/endpoints/{endpoint}/chat/completions"
    )
    response = requests.post(
        url,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        json={
            "model": "google_medgemma-27b-it",
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": BLIND_PROMPT},
                        {"type": "image_url", "image_url": {"url": f"data:{mime_type};base64,{encoded}"}},
                    ],
                }
            ],
            "temperature": 0.1,
            "max_tokens": 500,
        },
        timeout=120,
    )
    if response.status_code != 200:
        raise RuntimeError(f"MedGemma gcloud-token endpoint returned {response.status_code}: {response.text[:500]}")
    data = response.json()
    content = data.get("choices", [{}])[0].get("message", {}).get("content", "")
    if not content:
        raise RuntimeError(f"MedGemma gcloud-token call returned empty content: {str(data)[:500]}")
    return content


def evaluate_sample(sample: dict[str, Any], use_llm_judge: bool) -> dict[str, Any]:
    result = call_medgemma(sample["image_path"])
    parsed = parse_json(result["raw"]) if result["ok"] else None
    text = finding_text(parsed, result["raw"])
    predicted = detected_labels(text) if result["ok"] else []
    overlap = caption_overlap(sample["baseline_caption"], text)
    fallback_judge = deterministic_judge(sample["true_labels"], predicted, parsed is not None)
    judge = llm_judge(result["raw"], sample, predicted, fallback_judge) if result["ok"] and use_llm_judge else fallback_judge

    true_set = set(sample["true_labels"])
    pred_set = set(predicted)
    return {
        **sample,
        "status": "ok" if result["ok"] else "error",
        "error": result["error"],
        "latency_ms": result["latency_ms"],
        "auth_source": result["auth_source"],
        "raw_output": result["raw"],
        "parsed_output": parsed,
        "parse_ok": parsed is not None,
        "finding_text": text,
        "detected_labels": predicted,
        "caption_overlap": overlap,
        "label_counts": {
            "tp": len(true_set & pred_set),
            "fp": len(pred_set - true_set),
            "fn": len(true_set - pred_set),
            "false_positive_labels": sorted(pred_set - true_set),
            "missed_labels": sorted(true_set - pred_set),
        },
        "pneumonia_detected": "Pneumonia" in pred_set,
        "judge": judge,
    }


def summarize(results: list[dict[str, Any]]) -> dict[str, Any]:
    ok_results = [r for r in results if r["status"] == "ok"]
    latencies = [r["latency_ms"] for r in ok_results]
    per_label = {}
    total_tp = total_fp = total_fn = 0
    pneumonia_tp = pneumonia_fn = 0
    hallucinated = 0
    detected_total = 0

    for label in ALL_LABELS:
        tp = fp = fn = 0
        for result in ok_results:
            true_set = set(result["true_labels"])
            pred_set = set(result["detected_labels"])
            if label in true_set and label in pred_set:
                tp += 1
            elif label not in true_set and label in pred_set:
                fp += 1
            elif label in true_set and label not in pred_set:
                fn += 1
        precision = tp / (tp + fp) if tp + fp else 0.0
        recall = tp / (tp + fn) if tp + fn else 0.0
        f1 = 2 * precision * recall / (precision + recall) if precision + recall else 0.0
        per_label[label] = {
            "tp": tp,
            "fp": fp,
            "fn": fn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1": round(f1, 4),
        }
        total_tp += tp
        total_fp += fp
        total_fn += fn

    for result in ok_results:
        pred_set = set(result["detected_labels"])
        true_set = set(result["true_labels"])
        detected_total += len(pred_set)
        hallucinated += len(pred_set - true_set)
        if "Pneumonia" in pred_set:
            pneumonia_tp += 1
        else:
            pneumonia_fn += 1

    micro_precision = total_tp / (total_tp + total_fp) if total_tp + total_fp else 0.0
    micro_recall = total_tp / (total_tp + total_fn) if total_tp + total_fn else 0.0
    micro_f1 = (
        2 * micro_precision * micro_recall / (micro_precision + micro_recall)
        if micro_precision + micro_recall
        else 0.0
    )

    return {
        "num_samples": len(results),
        "successful_calls": len(ok_results),
        "api_error_rate": round((len(results) - len(ok_results)) / max(len(results), 1), 4),
        "json_parse_rate": round(
            sum(1 for r in ok_results if r["parse_ok"]) / max(len(ok_results), 1), 4
        ),
        "pneumonia_detection": {
            "tp": pneumonia_tp,
            "fn": pneumonia_fn,
            "recall": round(pneumonia_tp / max(pneumonia_tp + pneumonia_fn, 1), 4),
        },
        "label_micro": {
            "precision": round(micro_precision, 4),
            "recall": round(micro_recall, 4),
            "f1": round(micro_f1, 4),
            "tp": total_tp,
            "fp": total_fp,
            "fn": total_fn,
        },
        "hallucination_rate": round(hallucinated / max(detected_total, 1), 4),
        "caption_overlap_mean_recall": round(
            statistics.mean([r["caption_overlap"]["recall"] for r in ok_results]) if ok_results else 0.0,
            4,
        ),
        "judge_score_mean": round(
            statistics.mean([r["judge"]["score"] for r in ok_results]) if ok_results else 0.0,
            2,
        ),
        "latency_ms": {
            "mean": round(statistics.mean(latencies), 2) if latencies else 0.0,
            "median": round(statistics.median(latencies), 2) if latencies else 0.0,
            "p95": round(sorted(latencies)[min(int(0.95 * len(latencies)), len(latencies) - 1)], 2)
            if latencies
            else 0.0,
        },
        "per_label": per_label,
    }


def write_markdown(output: dict[str, Any], path: Path) -> None:
    primary = output["primary_case"]
    summary = output["summary"]
    lines = [
        "# MedGemma Pneumonia Blind-Vision Validation",
        "",
        f"Generated: {output['timestamp']}",
        "",
        "## Run Configuration",
        "",
        f"- Model path: {output['model_path']}",
        f"- Pipeline mode: {output['pipeline_mode']}",
        f"- Prompt: `{output['prompt_excerpt']}`",
        f"- Cohort size: {summary['num_samples']} pneumonia-positive MIMIC-CXR images",
        f"- Primary image: `{primary['rel_path']}`",
        f"- Primary auth source: `{primary['auth_source']}`",
        f"- Baseline caption: `{primary['baseline_caption']}`",
        "",
        "## Primary Pneumonia Case",
        "",
        f"- Status: {primary['status']}",
        f"- True labels: {', '.join(primary['true_labels'])}",
        f"- Detected labels: {', '.join(primary['detected_labels']) or 'none'}",
        f"- Pneumonia detected: {primary['pneumonia_detected']}",
        f"- Caption token recall: {primary['caption_overlap']['recall']:.2%}",
        f"- Judge score: {primary['judge']['score']}/10 ({primary['judge']['source']})",
        f"- Judge reasoning: {primary['judge']['reasoning']}",
        "",
        "### Raw MedGemma Output",
        "",
        "```text",
        primary["raw_output"].strip(),
        "```",
        "",
        "## Cohort Grounding Numbers",
        "",
        f"- Successful calls: {summary['successful_calls']}/{summary['num_samples']}",
        f"- JSON parse rate: {summary['json_parse_rate']:.2%}",
        f"- Pneumonia recall: {summary['pneumonia_detection']['recall']:.2%} "
        f"({summary['pneumonia_detection']['tp']} TP, {summary['pneumonia_detection']['fn']} FN)",
        f"- Label micro precision: {summary['label_micro']['precision']:.2%}",
        f"- Label micro recall: {summary['label_micro']['recall']:.2%}",
        f"- Label micro F1: {summary['label_micro']['f1']:.2%}",
        f"- Hallucination rate: {summary['hallucination_rate']:.2%}",
        f"- Mean caption token recall: {summary['caption_overlap_mean_recall']:.2%}",
        f"- Mean judge score: {summary['judge_score_mean']}/10",
        f"- Latency: mean {summary['latency_ms']['mean']:.0f} ms, "
        f"median {summary['latency_ms']['median']:.0f} ms, P95 {summary['latency_ms']['p95']:.0f} ms",
        "",
        "## Per-Image Summary",
        "",
        "| Image | Caption | Detected Labels | Pneumonia | Judge | Caption Recall |",
        "|---|---|---|---|---:|---:|",
    ]
    for result in output["results"]:
        lines.append(
            "| `{}` | `{}` | {} | {} | {}/10 | {:.2%} |".format(
                result["dicom_id"],
                result["baseline_caption"],
                ", ".join(result["detected_labels"]) or "none",
                "yes" if result["pneumonia_detected"] else "no",
                result["judge"]["score"],
                result["caption_overlap"]["recall"],
            )
        )
    lines.extend(
        [
            "",
            "## Interpretation",
            "",
            "These results are grounded against the hidden MIMIC-CXR label caption for each image. "
            "Because Visual-RAG is disabled or unavailable in this environment, the run is reported as "
            "MedGemma blind vision without Visual-RAG anchoring rather than a fully anchored pipeline run.",
            "",
        ]
    )
    path.write_text("\n".join(lines), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--n", type=int, default=20)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--no-llm-judge", action="store_true")
    args = parser.parse_args()

    from src.runtime_config import ENABLE_VISUAL_RAG, VISION_PROVIDER

    samples = select_pneumonia_cohort(load_samples(), args.n, args.seed)
    print(f"Selected {len(samples)} pneumonia-positive samples.")
    print(f"Primary case: {samples[0]['rel_path']} | {samples[0]['baseline_caption']}")

    results = []
    for index, sample in enumerate(samples, 1):
        print(f"[{index}/{len(samples)}] {sample['dicom_id']} {sample['baseline_caption']}")
        evaluated = evaluate_sample(sample, use_llm_judge=not args.no_llm_judge)
        print(
            "  status={status} pneumonia={pneumonia} labels={labels} judge={judge}/10 latency={latency:.0f}ms".format(
                status=evaluated["status"],
                pneumonia=evaluated["pneumonia_detected"],
                labels=",".join(evaluated["detected_labels"]) or "none",
                judge=evaluated["judge"]["score"],
                latency=evaluated["latency_ms"],
            )
        )
        if evaluated["error"]:
            print(f"  error={evaluated['error'][:180]}")
        results.append(evaluated)

    timestamp = time.strftime("%Y%m%d_%H%M%S")
    summary = summarize(results)
    output = {
        "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
        "model_path": "Vertex AI MedGemma 27B via dedicated endpoint",
        "pipeline_mode": (
            "MedGemma blind vision with Visual-RAG enabled"
            if ENABLE_VISUAL_RAG
            else "MedGemma blind vision without Visual-RAG anchoring"
        ),
        "runtime_config": {
            "vision_provider": VISION_PROVIDER,
            "enable_visual_rag": ENABLE_VISUAL_RAG,
            "vertex_dedicated_domain_set": bool(os.getenv("VERTEX_DEDICATED_DOMAIN")),
            "judge_model": os.getenv("BLIND_VISION_JUDGE_MODEL", "google/gemma-3-4b-it:free")
            if not args.no_llm_judge
            else "deterministic_gemma_style_rubric",
        },
        "prompt_excerpt": "Interpret this scan blindly and detail any pathological findings.",
        "primary_case": results[0],
        "summary": summary,
        "results": results,
    }

    results_dir = REPO_ROOT / "results"
    report_dir = REPO_ROOT / "report" / "Eval Reports" / "Outputs"
    results_dir.mkdir(parents=True, exist_ok=True)
    report_dir.mkdir(parents=True, exist_ok=True)

    json_path = results_dir / f"blind_vision_pneumonia_{timestamp}.json"
    md_path = report_dir / f"blind_vision_pneumonia_{timestamp}.md"
    json_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    write_markdown(output, md_path)

    print("\nWrote:")
    print(f"  {json_path}")
    print(f"  {md_path}")
    print("\nSummary:")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
