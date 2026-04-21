# Phase 3 Validation: Clinician Workflow

This phase validates the end-to-end user experience for healthcare providers using the TrustMed AI Clinician Dashboard.

## Summary Table

| Test ID | Objective | Input / Steps | Observation | Issues | Result |
|---|---|---|---|---|---|
| **CLI-001** | Open Dashboard | Navigate to `/clinician` | UI loads with sidebar and main workspace. | None | **PASS** |
| **CLI-002** | Create Session | Click 'New Chat' | System generates a unique session ID and clears workspace. | None | **PASS** |
| **CLI-003** | Load Patient | Select Patient `10002428` | Dashboard populates with vitals, history, and medications. | None | **PASS** |
| **CLI-004** | Text Query | Ask: "Summarize risks" | AI streams response using patient context. | None | **PASS** |
| **CLI-005** | SOAP Generation | Click 'Generate SOAP Note' | System successfully generates a structured clinical note. | None | **PASS** |
| **CLI-006** | Graph View | Inspect Knowledge Graph | Relationship nodes for patient 10002428 render in 3D. | None | **PASS** |
| **CLI-007** | Image Upload | Upload `roco_0001.jpg` | Image previews and is correctly attached to chat session. | None | **PASS** |
| **CLI-008** | Figure Panels | Upload `compound_figure.png` | System detects 4 sub-panels and allows focused analysis. | None | **PASS** |
| **CLI-009** | Model Toggle | Switch LLM models | UI swaps between reasoning and fast models. | None | **PASS** |
| **CLI-010** | Persistence | Refresh browser page | Page returns to a blank "New Chat" state. | **BUG-002**: Session state is not persisted in LocalStorage/URL. | **FAIL** |

## Issue Details

### Vision: Figure Panel Detection
- **Observation**: The subfigure detector correctly identifies panels in standard journal figures with white separators (verified with `compound_figure.png`). 
- **Limitation**: Raw medical scans with black backgrounds/separators are currently not supported by the default threshold and remain a future enhancement area.

### BUG-002: Session State Loss on Refresh
- **Observation**: Hard refreshing the browser results in all active patient context and chat history being cleared from the immediate view.
- **Root Cause**: The frontend state is held entirely in React memory without a background sync to `localStorage` or session-specific URL routing.

## Conclusion
Core clinical functions (Search, RAG, SOAP, Graph) are fully operational. However, the system is hindered by **usability issues** regarding session persistence and **vision detection limitations** for dark-background medical figures.
