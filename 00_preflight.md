# Phase 0 - Preflight Validation Report

- **Run ID:** 20260420_MANUAL
- **Generated at:** 2026-04-20 15:30:00
- **Status:** PASS

## Test Summary

| Test ID | Objective | Input | Status | Output |
| :--- | :--- | :--- | :--- | :--- |
| **ENV-001** | Python Version | `python3 --version` | **PASS** | Python 3.13.12 |
| **ENV-002** | Node Version | `node --version` | **PASS** | v22.22.0 |
| **ENV-003** | npm Version | `npm --version` | **PASS** | 10.9.4 |
| **ENV-004** | Python Deps | `python3 -c "import fastapi..."` | **PASS** | python_deps_ok |
| **ENV-005** | Frontend Manifest | `test -f "./frontend/package.json"` | **PASS** | True |
| **ENV-006** | .env Presence | `test -f ".env"` | **PASS** | True |
| **ENV-007** | Env Keys | `python3 -c "check_keys"` | **PASS** | All keys True |
| **ENV-008** | SQLite Demo DB | `test -f "./data/mimic_demo.db"` | **PASS** | True |
| **ENV-009** | Chroma DB | `test -d "./data/chroma_db"` | **PASS** | True |
| **ENV-010** | Neo4j Connect | `python3 -c "verify_neo4j"` | **PASS** | neo4j_ok |
| **ENV-011** | Runtime Dirs | `python3 -c "import api.main"` | **PASS** | runtime_dirs_ok |
| **ENV-012** | Git SHA | `git rev-parse HEAD` | **PASS** | 741b68e095... |

## Detailed Observations

### ENV-001 - Python Version
- **Observation:** Python 3.13.12 detected.
- **Output:** `Python 3.13.12`

### ENV-007 - Env Keys
- **Observation:** All keys (OPENROUTER_API_KEY, NEO4J_URI, NEO4J_USERNAME, NEO4J_PASSWORD) are present and valid.

### ENV-010 - Neo4j Connectivity
- **Observation:** Successfully verified connectivity to the Neo4j Graph database.
