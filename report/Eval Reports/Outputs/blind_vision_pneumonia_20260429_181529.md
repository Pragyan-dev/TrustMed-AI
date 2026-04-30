# MedGemma Pneumonia Blind-Vision Validation

Generated: 2026-04-29 18:15:29

## Run Configuration

- Model path: Vertex AI MedGemma 27B via dedicated endpoint
- Pipeline mode: MedGemma blind vision without Visual-RAG anchoring
- Prompt: `Interpret this scan blindly and detail any pathological findings.`
- Cohort size: 20 pneumonia-positive MIMIC-CXR images
- Primary image: `files/p10/p10001884/s50807032/ebf48d65-7e780cd5-59118fba-50977097-3720cc7e.jpg`
- Primary auth source: `gcloud_user_token_after_adc_error: MedGemma endpoint returned 403: {"error":{"code":403,"message":"Permission 'aiplatform.googleapis.com/endpoints.predict' denied on resource 'projects/project-49cb6588-0f38-4c89-883`
- Baseline caption: `Chest X-ray - Pneumonia`

## Primary Pneumonia Case

- Status: ok
- True labels: Pneumonia
- Detected labels: Cardiomegaly, Consolidation, Pleural Effusion, Support Devices
- Pneumonia detected: False
- Caption token recall: 0.00%
- Judge score: 6/10 (google/gemma-3-4b-it:free)
- Judge reasoning: The report identifies relevant findings like consolidation and cardiomegaly, aligning with the ground truth. However, it misses explicitly stating pneumonia and overstates the certainty of some findings (e.g., pleural effusion). The overall impression is somewhat vague. Safety is high as it doesn't suggest a diagnosis without qualification.

### Raw MedGemma Output

```text
```json{"modality": "X-Ray","body_region": "Chest","high_confidence_findings": [{"finding": "Increased interstitial markings bilaterally, predominantly in the lower lobes", "confidence": "HIGH"},{"finding": "Hilar prominence bilaterally", "confidence": "HIGH"},{"finding": "Kerley B lines visible at the lung bases", "confidence": "HIGH"},{"finding": "Possible cardiomegaly", "confidence": "HIGH"}],"uncertain_findings": [{"finding": "Possible pleural effusions, difficult to assess definitively", "confidence": "LOW"},{"finding": "Possible consolidation in the right lower lobe", "confidence": "LOW"}],"cannot_assess": ["Mediastinal structures obscured by overlying structures", "Subtle lung parenchymal changes"],"overall_impression": "The chest X-ray shows findings suggestive of interstitial lung disease with possible cardiomegaly and potential pleural effusions. Further evaluation may be needed."}```
```

## Cohort Grounding Numbers

- Successful calls: 20/20
- JSON parse rate: 100.00%
- Pneumonia recall: 5.00% (1 TP, 19 FN)
- Label micro precision: 1.33%
- Label micro recall: 5.00%
- Label micro F1: 2.11%
- Hallucination rate: 98.67%
- Mean caption token recall: 5.00%
- Mean judge score: 5.2/10
- Latency: mean 10634 ms, median 10487 ms, P95 13522 ms

## Per-Image Summary

| Image | Caption | Detected Labels | Pneumonia | Judge | Caption Recall |
|---|---|---|---|---:|---:|
| `ebf48d65-7e780cd5-59118fba-50977097-3720cc7e` | `Chest X-ray - Pneumonia` | Cardiomegaly, Consolidation, Pleural Effusion, Support Devices | no | 6/10 | 0.00% |
| `81601813-88063656-fdacf6b6-2f97c7dd-ace5238e` | `Chest X-ray - Pneumonia` | Fracture, Pleural Effusion, Pleural Other | no | 3/10 | 0.00% |
| `544f24a2-50daa522-4728a5b8-586a6aad-87bc1e19` | `Chest X-ray - Pneumonia` | Consolidation, Enlarged Cardiomediastinum, Pleural Effusion, Pneumothorax | no | 6/10 | 0.00% |
| `52fc3f2b-69a2b240-317815c6-e2fbaad8-5b949071` | `Chest X-ray - Pneumonia` | Atelectasis | no | 3/10 | 0.00% |
| `ef4e1a62-3c4cf1e2-5d8249ed-c6fe877a-b8338359` | `Chest X-ray - Pneumonia` | Consolidation, Enlarged Cardiomediastinum, Pleural Effusion, Pneumothorax | no | 6/10 | 0.00% |
| `48d8cddc-08d857dd-b1c78ae4-cf761a4c-858bbb55` | `Chest X-ray - Pneumonia` | Cardiomegaly, Edema, Enlarged Cardiomediastinum | no | 6/10 | 0.00% |
| `30a6e204-97075257-99faafcf-7922da44-19215374` | `Chest X-ray - Pneumonia` | Consolidation, Enlarged Cardiomediastinum, Pleural Effusion, Pneumothorax | no | 3/10 | 0.00% |
| `2a20971f-e21cce85-f829ffc5-0088916b-503fc6f0` | `Chest X-ray - Pneumonia` | Enlarged Cardiomediastinum | no | 3/10 | 0.00% |
| `1661a1dc-ac27300e-9346bb0c-521a42be-94b04774` | `Chest X-ray - Pneumonia` | Consolidation, Enlarged Cardiomediastinum, Lung Lesion, Pleural Effusion | no | 6/10 | 0.00% |
| `e5ba5704-ce2f09d3-e28fe2a2-8a9aca96-86f4966a` | `Chest X-ray - Pneumonia` | Consolidation, Enlarged Cardiomediastinum, Pleural Effusion, Pneumothorax | no | 3/10 | 0.00% |
| `cb163f0c-4a66ea4b-abb3a5a0-45e075f5-411bd65b` | `Chest X-ray - Pneumonia` | Atelectasis, Enlarged Cardiomediastinum, Lung Opacity, Pleural Effusion, Pneumothorax | no | 6/10 | 0.00% |
| `232bcc7f-82a2e28d-e6fcb4b2-c6df2736-ecc560b9` | `Chest X-ray - Pneumonia` | Enlarged Cardiomediastinum, Pleural Effusion, Pneumothorax | no | 6/10 | 0.00% |
| `31f2acf3-ea1efb47-15240664-248f9355-86bce5c4` | `Chest X-ray - Pneumonia` | Consolidation, Enlarged Cardiomediastinum, Pleural Effusion, Pneumothorax | no | 6/10 | 0.00% |
| `5284889c-58e61f8e-21c18eef-2710faf0-f40b5cdc` | `Chest X-ray - Pneumonia` | Atelectasis, Consolidation, Lung Lesion, Pleural Effusion, Pleural Other | no | 5/10 | 0.00% |
| `22f19fd3-f465ce1a-bc3983dd-0f023049-6907a34b` | `Chest X-ray - Pneumonia` | Enlarged Cardiomediastinum, Pleural Effusion, Pneumothorax | no | 3/10 | 0.00% |
| `99a21117-e67fd3ec-a82ea961-aa3d9059-0dd65cfb` | `Chest X-ray - Pneumonia` | Consolidation, Enlarged Cardiomediastinum, Pleural Effusion, Pneumothorax | no | 4/10 | 0.00% |
| `59dc2236-20967bcd-c86607da-3b6905f0-a8c0812a` | `Chest X-ray - Pneumonia` | Fracture | no | 8/10 | 0.00% |
| `cc0b5db2-cc391879-a10b0ccf-5e554f89-37f1cf99` | `Chest X-ray - Pneumonia` | Cardiomegaly, Consolidation, Edema, Lung Opacity, Pleural Effusion, Support Devices | no | 5/10 | 0.00% |
| `2f5e274a-749f1c06-1c8be147-4fabf575-e333e808` | `Chest X-ray - Pneumonia` | Consolidation, Enlarged Cardiomediastinum, Lung Opacity, Pleural Effusion, Pneumothorax, Support Devices | no | 8/10 | 0.00% |
| `cb51e040-4d99db13-6fb28d7e-9939ff56-e827a1f6` | `Chest X-ray - Pneumonia` | Cardiomegaly, Edema, Lung Opacity, Pleural Effusion, Pneumonia, Support Devices | yes | 8/10 | 100.00% |

## Interpretation

These results are grounded against the hidden MIMIC-CXR label caption for each image. Because Visual-RAG is disabled or unavailable in this environment, the run is reported as MedGemma blind vision without Visual-RAG anchoring rather than a fully anchored pipeline run.
