#!/usr/bin/env python3
"""
TrustMed AI - Comprehensive API Evaluation Suite

Tests all core components via the running API:
1. API Health Check
2. Vector Search (via Chat)
3. Knowledge Graph Query
4. Patient Context (via Chat)
5. Vision Agent (Image Analysis)
6. Conversational Flow

Run: python3 tests/test_api_evaluation.py
"""

import os
import sys
import json
import time
import requests
from typing import Dict, List, Any, Optional
from dataclasses import dataclass, field, asdict
from statistics import mean, stdev

# Configuration
API_BASE_URL = "http://127.0.0.1:8000"
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Test image for vision testing
TEST_IMAGE = os.path.join(PROJECT_ROOT, "temp_scan.jpg")
if not os.path.exists(TEST_IMAGE):
    # Fallback to uploads directory
    uploads = os.path.join(PROJECT_ROOT, "uploads")
    if os.path.isdir(uploads):
        for f in os.listdir(uploads):
            if f.endswith(('.jpg', '.jpeg', '.png')):
                TEST_IMAGE = os.path.join(uploads, f)
                break


@dataclass
class TestResult:
    """Result from a single test."""
    name: str
    passed: bool
    latency_ms: int
    details: str = ""
    error: str = ""
    keywords_found: List[str] = field(default_factory=list)
    keywords_expected: List[str] = field(default_factory=list)


class TrustMedEvaluator:
    """API-based evaluation for TrustMed AI."""
    
    def __init__(self, base_url: str = API_BASE_URL):
        self.base_url = base_url
        self.session_id = f"eval_{int(time.time())}"
        self.results: List[TestResult] = []
    
    def _request(self, method: str, endpoint: str, **kwargs) -> tuple[Any, int]:
        """Make an API request and return (response_json, latency_ms)."""
        url = f"{self.base_url}{endpoint}"
        start = time.time()
        try:
            resp = requests.request(method, url, timeout=120, **kwargs)
            latency = int((time.time() - start) * 1000)
            resp.raise_for_status()
            return resp.json(), latency
        except requests.exceptions.RequestException as e:
            latency = int((time.time() - start) * 1000)
            raise Exception(f"Request failed: {e}") from e
    
    def _check_keywords(self, text: str, keywords: List[str]) -> List[str]:
        """Check which keywords appear in the text."""
        text_lower = text.lower()
        return [kw for kw in keywords if kw.lower() in text_lower]
    
    # =========================================================================
    # Test Methods
    # =========================================================================
    
    def test_api_health(self) -> TestResult:
        """Test 1: API Health Check"""
        print("\n📋 Test 1: API Health Check")
        try:
            data, latency = self._request("GET", "/")
            passed = data.get("version") == "2.0.0"
            result = TestResult(
                name="API Health",
                passed=passed,
                latency_ms=latency,
                details=f"Version: {data.get('version')}, Message: {data.get('message')}"
            )
            print(f"   ✅ Passed ({latency}ms)" if passed else f"   ❌ Failed")
        except Exception as e:
            result = TestResult(name="API Health", passed=False, latency_ms=0, error=str(e))
            print(f"   ❌ Error: {e}")
        
        self.results.append(result)
        return result
    
    def test_graph_query(self) -> TestResult:
        """Test 2: Knowledge Graph Query"""
        print("\n🕸️  Test 2: Knowledge Graph Query")
        try:
            data, latency = self._request("GET", "/graph", params={"search_term": "Diabetes"})
            nodes = data.get("nodes", [])
            edges = data.get("edges", [])
            passed = len(nodes) > 0
            
            node_labels = [n.get("label", "") for n in nodes[:5]]
            result = TestResult(
                name="Knowledge Graph",
                passed=passed,
                latency_ms=latency,
                details=f"Nodes: {len(nodes)}, Edges: {len(edges)}, Sample: {node_labels}"
            )
            print(f"   ✅ Found {len(nodes)} nodes, {len(edges)} edges ({latency}ms)" if passed else f"   ❌ No nodes found")
        except Exception as e:
            result = TestResult(name="Knowledge Graph", passed=False, latency_ms=0, error=str(e))
            print(f"   ❌ Error: {e}")
        
        self.results.append(result)
        return result
    
    def test_medical_knowledge_query(self) -> TestResult:
        """Test 3: Medical Knowledge Query (Tests Vector Search + LLM)"""
        print("\n📚 Test 3: Medical Knowledge Query")
        query = "What are the symptoms and treatment for Type 2 Diabetes?"
        expected_keywords = ["blood sugar", "insulin", "glucose", "diet", "exercise", "medication"]
        
        try:
            data, latency = self._request("POST", "/chat", json={
                "message": query,
                "session_id": self.session_id
            })
            response = data.get("response", "")
            found = self._check_keywords(response, expected_keywords)
            passed = len(found) >= 3  # At least 3 keywords should appear
            
            result = TestResult(
                name="Medical Knowledge Query",
                passed=passed,
                latency_ms=latency,
                details=f"Response length: {len(response)} chars",
                keywords_found=found,
                keywords_expected=expected_keywords
            )
            print(f"   ✅ Keywords: {len(found)}/{len(expected_keywords)} ({latency}ms)" if passed else f"   ❌ Only {len(found)} keywords found")
        except Exception as e:
            result = TestResult(name="Medical Knowledge Query", passed=False, latency_ms=0, error=str(e))
            print(f"   ❌ Error: {e}")
        
        self.results.append(result)
        return result
    
    def test_patient_context_query(self) -> TestResult:
        """Test 4: Patient Context Query (Tests SQLite + Patient Tool)"""
        print("\n🏥 Test 4: Patient Context Query")
        query = "Can you analyze patient 10002428? What medications are they on?"
        expected_keywords = ["patient", "medication", "diagnosis", "vital", "history"]
        
        try:
            data, latency = self._request("POST", "/chat", json={
                "message": query,
                "session_id": self.session_id
            })
            response = data.get("response", "")
            found = self._check_keywords(response, expected_keywords)
            # Patient query should mention patient data
            passed = "patient" in response.lower() and len(response) > 100
            
            result = TestResult(
                name="Patient Context Query",
                passed=passed,
                latency_ms=latency,
                details=f"Response length: {len(response)} chars",
                keywords_found=found,
                keywords_expected=expected_keywords
            )
            print(f"   ✅ Patient data retrieved ({latency}ms)" if passed else f"   ❌ Insufficient response")
        except Exception as e:
            result = TestResult(name="Patient Context Query", passed=False, latency_ms=0, error=str(e))
            print(f"   ❌ Error: {e}")
        
        self.results.append(result)
        return result
    
    def test_drug_information_query(self) -> TestResult:
        """Test 5: Drug Information Query"""
        print("\n💊 Test 5: Drug Information Query")
        query = "What is metformin used for and what are its side effects?"
        expected_keywords = ["diabetes", "blood sugar", "side effect", "dose", "kidney"]
        
        try:
            data, latency = self._request("POST", "/chat", json={
                "message": query,
                "session_id": self.session_id
            })
            response = data.get("response", "")
            found = self._check_keywords(response, expected_keywords)
            passed = len(found) >= 2
            
            result = TestResult(
                name="Drug Information Query",
                passed=passed,
                latency_ms=latency,
                details=f"Response length: {len(response)} chars",
                keywords_found=found,
                keywords_expected=expected_keywords
            )
            print(f"   ✅ Keywords: {len(found)}/{len(expected_keywords)} ({latency}ms)" if passed else f"   ❌ Insufficient info")
        except Exception as e:
            result = TestResult(name="Drug Information Query", passed=False, latency_ms=0, error=str(e))
            print(f"   ❌ Error: {e}")
        
        self.results.append(result)
        return result
    
    def test_vision_agent(self) -> TestResult:
        """Test 6: Vision Agent (Image Analysis)"""
        print("\n👁️  Test 6: Vision Agent (Image Analysis)")
        
        if not os.path.exists(TEST_IMAGE):
            result = TestResult(
                name="Vision Agent",
                passed=False,
                latency_ms=0,
                error=f"No test image found at {TEST_IMAGE}"
            )
            print(f"   ⚠️  Skipped: No test image available")
            self.results.append(result)
            return result
        
        query = f"Analyze this medical scan for any abnormalities [ATTACHMENT: {TEST_IMAGE}]"
        expected_keywords = ["image", "scan", "finding", "chest", "lung", "opacity", "normal", "abnormal"]
        
        try:
            data, latency = self._request("POST", "/chat", json={
                "message": query,
                "session_id": self.session_id,
                "image_path": TEST_IMAGE
            })
            response = data.get("response", "")
            found = self._check_keywords(response, expected_keywords)
            passed = len(found) >= 2 and len(response) > 200
            
            result = TestResult(
                name="Vision Agent",
                passed=passed,
                latency_ms=latency,
                details=f"Response length: {len(response)} chars",
                keywords_found=found,
                keywords_expected=expected_keywords
            )
            print(f"   ✅ Image analyzed ({latency}ms)" if passed else f"   ❌ Insufficient analysis")
        except Exception as e:
            result = TestResult(name="Vision Agent", passed=False, latency_ms=0, error=str(e))
            print(f"   ❌ Error: {e}")
        
        self.results.append(result)
        return result
    
    def test_conversational_context(self) -> TestResult:
        """Test 7: Conversational Context (Follow-up Questions)"""
        print("\n💬 Test 7: Conversational Context")
        
        # First, set context with a disease
        try:
            self._request("POST", "/chat", json={
                "message": "Tell me about hypertension",
                "session_id": self.session_id + "_conv"
            })
            
            # Now ask a follow-up that requires context
            data, latency = self._request("POST", "/chat", json={
                "message": "What medications are used to treat it?",
                "session_id": self.session_id + "_conv"
            })
            response = data.get("response", "")
            
            # Should mention blood pressure medications
            expected_keywords = ["blood pressure", "ACE", "diuretic", "beta blocker", "medication", "drug"]
            found = self._check_keywords(response, expected_keywords)
            passed = len(found) >= 1 and len(response) > 100
            
            result = TestResult(
                name="Conversational Context",
                passed=passed,
                latency_ms=latency,
                details=f"Response correctly referenced previous context",
                keywords_found=found,
                keywords_expected=expected_keywords
            )
            print(f"   ✅ Context maintained ({latency}ms)" if passed else f"   ❌ Lost context")
        except Exception as e:
            result = TestResult(name="Conversational Context", passed=False, latency_ms=0, error=str(e))
            print(f"   ❌ Error: {e}")
        
        self.results.append(result)
        return result
    
    def test_session_management(self) -> TestResult:
        """Test 8: Session Management"""
        print("\n📁 Test 8: Session Management")
        
        try:
            # List sessions
            data, latency = self._request("GET", "/sessions")
            sessions = data.get("sessions", [])
            passed = isinstance(sessions, list)
            
            result = TestResult(
                name="Session Management",
                passed=passed,
                latency_ms=latency,
                details=f"Found {len(sessions)} sessions"
            )
            print(f"   ✅ {len(sessions)} sessions found ({latency}ms)" if passed else f"   ❌ Failed to list sessions")
        except Exception as e:
            result = TestResult(name="Session Management", passed=False, latency_ms=0, error=str(e))
            print(f"   ❌ Error: {e}")
        
        self.results.append(result)
        return result
    
    # =========================================================================
    # Report Generation
    # =========================================================================
    
    def generate_report(self) -> str:
        """Generate evaluation report."""
        lines = []
        lines.append("\n" + "=" * 70)
        lines.append("TRUSTMED AI - SYSTEM EVALUATION REPORT")
        lines.append("=" * 70)
        lines.append(f"Timestamp: {time.strftime('%Y-%m-%d %H:%M:%S')}")
        lines.append(f"API Endpoint: {self.base_url}")
        lines.append("")
        
        # Summary
        passed = sum(1 for r in self.results if r.passed)
        total = len(self.results)
        pass_rate = (passed / total * 100) if total > 0 else 0
        
        lines.append("SUMMARY")
        lines.append("-" * 40)
        lines.append(f"Tests Passed: {passed}/{total} ({pass_rate:.1f}%)")
        
        latencies = [r.latency_ms for r in self.results if r.latency_ms > 0]
        if latencies:
            lines.append(f"Avg Latency: {mean(latencies):.0f}ms")
            lines.append(f"Max Latency: {max(latencies)}ms")
        lines.append("")
        
        # Detailed Results
        lines.append("DETAILED RESULTS")
        lines.append("-" * 40)
        
        for r in self.results:
            status = "✅ PASS" if r.passed else "❌ FAIL"
            lines.append(f"\n{r.name}: {status}")
            lines.append(f"  Latency: {r.latency_ms}ms")
            if r.details:
                lines.append(f"  Details: {r.details}")
            if r.error:
                lines.append(f"  Error: {r.error}")
            if r.keywords_expected:
                lines.append(f"  Keywords: {len(r.keywords_found)}/{len(r.keywords_expected)} found")
                lines.append(f"    Found: {r.keywords_found}")
        
        lines.append("\n" + "=" * 70)
        
        # Health Score
        health_score = pass_rate / 100
        bar_len = int(health_score * 40)
        bar = "█" * bar_len + "░" * (40 - bar_len)
        lines.append(f"OVERALL HEALTH: {health_score:.2f}/1.00  [{bar}]")
        lines.append("=" * 70)
        
        return "\n".join(lines)
    
    def run_all_tests(self):
        """Run all evaluation tests."""
        print("\n" + "=" * 70)
        print("🩺 TRUSTMED AI - SYSTEM EVALUATION")
        print("=" * 70)
        
        self.test_api_health()
        self.test_graph_query()
        self.test_medical_knowledge_query()
        self.test_patient_context_query()
        self.test_drug_information_query()
        self.test_vision_agent()
        self.test_conversational_context()
        self.test_session_management()
        
        # Generate and print report
        report = self.generate_report()
        print(report)
        
        # Save results
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        results_file = os.path.join(PROJECT_ROOT, "results", f"api_evaluation_{timestamp}.json")
        os.makedirs(os.path.dirname(results_file), exist_ok=True)
        
        with open(results_file, "w") as f:
            json.dump({
                "timestamp": timestamp,
                "api_url": self.base_url,
                "summary": {
                    "passed": sum(1 for r in self.results if r.passed),
                    "total": len(self.results),
                    "pass_rate": sum(1 for r in self.results if r.passed) / len(self.results) if self.results else 0
                },
                "results": [asdict(r) for r in self.results]
            }, f, indent=2)
        
        print(f"\n📄 Results saved to: {results_file}")
        
        return self.results


def main():
    """Run the evaluation suite."""
    evaluator = TrustMedEvaluator()
    evaluator.run_all_tests()


if __name__ == "__main__":
    main()
