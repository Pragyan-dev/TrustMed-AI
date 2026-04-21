# Phase 2 - API Contract Validation Report (Full Suite)

- **Run ID:** 20260420_MANUAL_PH2_COMPLETE
- **Generated at:** 2026-04-20 16:17:20
- **Overall Status:** PASS

## Summary Matrix

| ID | Input | Observation | Issues | Results |
| :--- | :--- | :--- | :--- | :--- |
| **API-001** | `curl -s /` | Health check ok | None | **PASS** |
| **API-002** | `curl -X POST /sessions/new` | Created a744a9cf5... | None | **PASS** |
| **API-003** | `curl -s /sessions` | Session shown in list | None | **PASS** |
| **API-004** | `curl -s /sessions/{id}` | Metadata retrieved | None | **PASS** |
| **API-005** | `curl -s /patient/{id}` | Chart data received | None | **PASS** |
| **API-006** | `curl -X POST /summary` | LLM summary content ok | None | **PASS** |
| **API-007** | `curl -s /sessions` | Global list ok | None | **PASS** |
| **API-008** | `curl /explain-term` | Cache hit confirmed | None | **PASS** |
| **API-009** | `curl /graph` | 15 nodes / 14 edges | None | **PASS** |
| **API-010** | `curl -X POST /chat` | Medical reply ok | None | **PASS** |
| **API-011** | `curl -X POST /chat` | Scope blocked (coding) | None | **PASS** |
| **API-012** | `curl -X POST /soap-note`| Note generated | None | **PASS** |
| **API-013** | `curl -N /chat/stream` | Multi-line SSE ok | None | **PASS** |
| **API-014** | `curl -X POST /rename` | Renamed successful | None | **PASS** |
| **API-015** | `curl -X DELETE` | Deleted successful | None | **PASS** |

## Detailed Breakdown (Sample)

### API-010: Chat Messaging
- **Input:** Medical query about diabetes.
- **Observation:** AI provided structured advice including clinical signs and next steps.
- **Issues:** None.
- **Results:** **PASS**

### API-013: Streaming Chat
- **Input:** Summary risk request with -N flag.
- **Observation:** Progress steps for patient data, graph, and safety displayed before tokens.
- **Issues:** None.
- **Results:** **PASS**
