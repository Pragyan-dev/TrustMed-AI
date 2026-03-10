#!/usr/bin/env python3
"""
Comprehensive test script for conversational context.
Tests multiple conversation scenarios with different topics and follow-ups.
"""
import os
import subprocess
import sys
import time

def run_query(query, session_file="chat_history.json"):
    """Run a query and return the output."""
    print(f"\n{'='*60}")
    print(f"QUERY: '{query}'")
    print('='*60)
    cmd = [sys.executable, "anti_test.py", "--query", query, "--session_file", session_file]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print("❌ Error running command:")
        print(result.stderr)
        return None
    
    return result.stdout

def extract_answer(output):
    """Extract the main answer from the output."""
    if not output:
        return ""
    
    lines = output.split('\n')
    answer_lines = []
    in_answer = False
    
    for line in lines:
        if "================== ANSWER ==================" in line:
            in_answer = True
            continue
        if "----------------- METRICS ------------------" in line:
            break
        if in_answer:
            answer_lines.append(line)
    
    return '\n'.join(answer_lines).strip()

def check_context_rewrite(output, expected_keyword):
    """Check if context rewriting happened and contains expected keyword."""
    if not output:
        return False, "No output"
    
    # Check if rewriting happened
    if "[Context] Rewrote query:" in output:
        # Extract the rewritten query
        for line in output.split('\n'):
            if "[Context] Rewrote query:" in line:
                rewritten = line.split("->")[1].strip() if "->" in line else ""
                if expected_keyword.lower() in rewritten.lower():
                    return True, f"✓ Rewritten to: {rewritten}"
                else:
                    return False, f"⚠ Rewritten but missing '{expected_keyword}': {rewritten}"
    
    return False, "No context rewriting detected"

def test_scenario(scenario_name, queries, session_file):
    """Test a conversation scenario."""
    print(f"\n\n{'#'*70}")
    print(f"# SCENARIO: {scenario_name}")
    print(f"{'#'*70}")
    
    results = []
    
    for i, query_info in enumerate(queries):
        query = query_info["query"]
        expected_keyword = query_info.get("expected_keyword", None)
        
        output = run_query(query, session_file)
        
        if output:
            answer = extract_answer(output)
            print(f"\nANSWER (first 300 chars):\n{answer[:300]}...")
            
            # Check context rewriting for follow-up queries
            if i > 0 and expected_keyword:
                success, msg = check_context_rewrite(output, expected_keyword)
                status = "✓" if success else "✗"
                print(f"\n{status} Context Check: {msg}")
                results.append({
                    "query": query,
                    "success": success,
                    "message": msg
                })
            else:
                results.append({
                    "query": query,
                    "success": True,
                    "message": "Initial query"
                })
        else:
            results.append({
                "query": query,
                "success": False,
                "message": "Query failed"
            })
        
        # Brief pause between queries
        time.sleep(0.5)
    
    return results

def main():
    """Run all test scenarios."""
    
    # Define test scenarios
    scenarios = [
        {
            "name": "Diabetes Prevention",
            "session_file": "test_diabetes.json",
            "queries": [
                {"query": "What are the signs of diabetes?"},
                {"query": "How to prevent it?", "expected_keyword": "diabetes"},
                {"query": "What medications are used for it?", "expected_keyword": "diabetes"}
            ]
        },
        {
            "name": "Heart Disease",
            "session_file": "test_heart.json",
            "queries": [
                {"query": "What causes heart disease?"},
                {"query": "What are the symptoms?", "expected_keyword": "heart"},
                {"query": "How is it diagnosed?", "expected_keyword": "heart"}
            ]
        },
        {
            "name": "Migraine Treatment",
            "session_file": "test_migraine.json",
            "queries": [
                {"query": "Tell me about migraine headaches"},
                {"query": "What treatments are available?", "expected_keyword": "migraine"},
                {"query": "Are there any home remedies for it?", "expected_keyword": "migraine"}
            ]
        },
        {
            "name": "Flu vs Cold",
            "session_file": "test_flu.json",
            "queries": [
                {"query": "What's the difference between flu and cold?"},
                {"query": "How long does it typically last?", "expected_keyword": "flu"},
                {"query": "When should I see a doctor for it?", "expected_keyword": "flu"}
            ]
        },
        {
            "name": "High Blood Pressure",
            "session_file": "test_bp.json",
            "queries": [
                {"query": "What is high blood pressure?"},
                {"query": "What lifestyle changes can help?", "expected_keyword": "blood pressure"},
                {"query": "Can it be reversed?", "expected_keyword": "blood pressure"}
            ]
        }
    ]
    
    # Clean up old session files
    for scenario in scenarios:
        session_file = scenario["session_file"]
        if os.path.exists(session_file):
            os.remove(session_file)
            print(f"Cleaned up {session_file}")
    
    # Run all scenarios
    all_results = {}
    for scenario in scenarios:
        results = test_scenario(
            scenario["name"],
            scenario["queries"],
            scenario["session_file"]
        )
        all_results[scenario["name"]] = results
    
    # Print summary
    print(f"\n\n{'='*70}")
    print("SUMMARY REPORT")
    print('='*70)
    
    total_tests = 0
    passed_tests = 0
    
    for scenario_name, results in all_results.items():
        print(f"\n{scenario_name}:")
        for result in results:
            total_tests += 1
            status = "✓" if result["success"] else "✗"
            if result["success"]:
                passed_tests += 1
            print(f"  {status} {result['query'][:50]}... - {result['message']}")
    
    print(f"\n{'='*70}")
    print(f"TOTAL: {passed_tests}/{total_tests} tests passed")
    print('='*70)
    
    # Clean up session files after testing
    print("\nCleaning up test session files...")
    for scenario in scenarios:
        session_file = scenario["session_file"]
        if os.path.exists(session_file):
            os.remove(session_file)
            print(f"  Removed {session_file}")

if __name__ == "__main__":
    main()
