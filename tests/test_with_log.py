#!/usr/bin/env python3
"""
Test script for conversational context with detailed logging.
Generates a comprehensive log file with questions, rewritten queries, and answers.
"""
import os
import subprocess
import sys
import time
from datetime import datetime

def run_query(query, session_file="chat_history.json"):
    """Run a query and return the output."""
    cmd = [sys.executable, "anti_test.py", "--query", query, "--session_file", session_file]
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    if result.returncode != 0:
        print(f"❌ Error running query: {query}")
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
        if in_answer and line.strip():
            answer_lines.append(line)
    
    return '\n'.join(answer_lines).strip()

def extract_rewrite(output):
    """Extract the rewritten query if present."""
    if not output:
        return None
    
    for line in output.split('\n'):
        if "[Context] Rewrote query:" in line:
            parts = line.split("->")
            if len(parts) >= 2:
                return parts[1].strip().strip("'\"")
    
    return None

def test_scenario(scenario_name, queries, session_file, log_file):
    """Test a conversation scenario and log results."""
    log_file.write(f"\n{'='*80}\n")
    log_file.write(f"SCENARIO: {scenario_name}\n")
    log_file.write(f"{'='*80}\n\n")
    
    print(f"\n{'#'*70}")
    print(f"# {scenario_name}")
    print(f"{'#'*70}")
    
    results = []
    
    for i, query_info in enumerate(queries):
        query = query_info["query"]
        expected_keyword = query_info.get("expected_keyword", None)
        
        print(f"\n  Query {i+1}: {query}")
        
        output = run_query(query, session_file)
        
        if output:
            answer = extract_answer(output)
            rewrite = extract_rewrite(output)
            
            # Log to file
            log_file.write(f"{'─'*80}\n")
            log_file.write(f"Q{i+1}: {query}\n")
            
            if rewrite:
                log_file.write(f"REWRITTEN: {rewrite}\n")
            
            log_file.write(f"\nA{i+1}:\n{answer}\n")
            log_file.write(f"{'─'*80}\n\n")
            
            # Check context rewriting for follow-up queries
            if i > 0 and expected_keyword:
                if rewrite and expected_keyword.lower() in rewrite.lower():
                    status = "✓"
                    success = True
                    msg = f"Rewritten correctly"
                else:
                    status = "✗"
                    success = False
                    msg = "Context issue"
                
                print(f"  {status} {msg}")
                results.append({"query": query, "success": success, "message": msg})
            else:
                results.append({"query": query, "success": True, "message": "Initial query"})
        else:
            log_file.write(f"Q{i+1}: {query}\n")
            log_file.write(f"ERROR: Query failed\n\n")
            results.append({"query": query, "success": False, "message": "Query failed"})
        
        time.sleep(0.5)
    
    return results

def main():
    """Run all test scenarios and generate log."""
    
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
    
    # Create log file
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    log_filename = f"conversation_test_log_{timestamp}.txt"
    
    print(f"\n{'='*70}")
    print(f"Running conversational context tests...")
    print(f"Log file: {log_filename}")
    print(f"{'='*70}")
    
    with open(log_filename, 'w', encoding='utf-8') as log_file:
        log_file.write(f"CONVERSATIONAL CONTEXT TEST LOG\n")
        log_file.write(f"Generated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}\n")
        log_file.write(f"{'='*80}\n")
        
        # Run all scenarios
        all_results = {}
        for scenario in scenarios:
            results = test_scenario(
                scenario["name"],
                scenario["queries"],
                scenario["session_file"],
                log_file
            )
            all_results[scenario["name"]] = results
        
        # Write summary to log
        log_file.write(f"\n\n{'='*80}\n")
        log_file.write(f"TEST SUMMARY\n")
        log_file.write(f"{'='*80}\n\n")
        
        total_tests = 0
        passed_tests = 0
        
        for scenario_name, results in all_results.items():
            log_file.write(f"{scenario_name}:\n")
            for result in results:
                total_tests += 1
                status = "✓" if result["success"] else "✗"
                if result["success"]:
                    passed_tests += 1
                log_file.write(f"  {status} {result['query']} - {result['message']}\n")
            log_file.write("\n")
        
        log_file.write(f"{'='*80}\n")
        log_file.write(f"TOTAL: {passed_tests}/{total_tests} tests passed ({100*passed_tests//total_tests}%)\n")
        log_file.write(f"{'='*80}\n")
    
    # Print summary to console
    print(f"\n{'='*70}")
    print(f"TEST SUMMARY")
    print(f"{'='*70}")
    
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
    print(f"Log saved to: {log_filename}")
    print(f"{'='*70}")
    
    # Clean up session files after testing
    for scenario in scenarios:
        session_file = scenario["session_file"]
        if os.path.exists(session_file):
            os.remove(session_file)

if __name__ == "__main__":
    main()
