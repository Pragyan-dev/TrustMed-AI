# Phase 3 Validation: Patient Workflow

This phase validates the patient-facing interface, focusing on plain-language translation of clinical data and safety guardrails.

## Summary Table

| Test ID | Objective | Input / Steps | Observation | Issues | Result |
|---|---|---|---|---|---|
| **PAT-001** | Open Portal | Navigate to `/patient` | UI loads successfully with 'Health Profile' default. | None | **PASS** |
| **PAT-002** | Load Summary | Select Patient `10002428` | Plain-language summary, vitals, and meds populate. | None | **PASS** |
| **PAT-003** | API Summary | POST `/patient/10002428/summary` | Valid JSON returned with clear conversational keys. | None | **PASS** |
| **PAT-004** | Patient Chat | Ask: "Explain my blood pressure" | AI provides clear explanation of the 145/83 reading. | None | **PASS** |
| **PAT-005** | Off-Topic Block | Ask: "Write me a Java program" | AI refuses off-topic request correctly. | None | **PASS** |
| **PAT-006** | Term Explanation| Ask: "What is tachycardia?" | AI defines term simply and relates it to patient's 94bpm. | None | **PASS** |
| **PAT-007** | Vitals Trends | View 'Vitals' tab | Trend cards and tooltips render correctly. | None | **PASS** |
| **PAT-008** | Med Explanation | View 'Medications' tab | Medication purposes are translated to plain language. | None | **PASS** |
| **PAT-009** | Persistence | Refresh page during session | Workspace resets to initial state; chat is lost. | **BUG-002**: Global state persistence failure. | **FAIL** |

## Key Findings

### Plain Language translation
The translation engine is highly effective. It successfully identifies that a heart rate of 94 bpm is "in a usual adult range" but "worth watching" when combined with high blood pressure, providing actionable but non-alarming context.

### Safety Guardrails
The medical-only scope limitation is working as expected in the patient path, effectively blocking non-health related queries like software development.

### Shared Persistence Bug
Confirmed that **BUG-002** (State loss on refresh) is a global issue affecting both Clinician and Patient views. Fix requires a unified `localStorage` or `SessionStorage` sync in the React `App.jsx` entry point.
