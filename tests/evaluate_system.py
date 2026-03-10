#!/usr/bin/env python3
"""
Lightweight Evaluation Suite for Agentic RAG System

Focuses on fast, automated metrics:
1. Retrieval Quality (Internal Metrics)
2. Conversational Context Accuracy
3. System Performance (Latency)
4. Ground Truth Evaluation (Keyword Matching)
"""

import os
import sys
import json
import time
import subprocess
import re
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, field, asdict
from statistics import mean, stdev


@dataclass
class EvaluationResult:
    """Results from a single query evaluation."""
    query: str
    answer: str = ""
    rewritten_query: str = ""
    
    # Retrieval Quality
    avg_similarity: float = 0.0
    strong_share: float = 0.0
    docs_used: int = 0
    
    # Context Accuracy
    context_rewrite_correct: bool = True
    expected_keywords: List[str] = field(default_factory=list)
    found_keywords: List[str] = field(default_factory=list)
    
    # Performance
    latency_ms: int = 0
    
    # Ground Truth
    keyword_match_score: float = 0.0


class RAGEvaluator:
    """Main evaluation class for the RAG system."""
    
    def __init__(self, session_file: str = "eval_history.json"):
        self.session_file = session_file
    
    def run_query(self, query: str) -> Tuple[str, str, Dict[str, Any], int]:
        """Run a single query through the RAG system."""
        start_time = time.time()
        
        cmd = [sys.executable, "anti_test.py", "--query", query, 
               "--session_file", self.session_file]
        result = subprocess.run(cmd, capture_output=True, text=True)
        
        latency_ms = int((time.time() - start_time) * 1000)
        
        if result.returncode != 0:
            print(f"    ✗ Error running query")
            return "", "", {}, latency_ms
        
        # Extract rewritten query
        rewritten = query  # default to original
        for line in result.stdout.split('\n'):
            if "[Context] Rewrote query:" in line:
                parts = line.split("->")
                if len(parts) > 1:
                    rewritten = parts[1].strip().strip("'\"")
        
        # Extract answer and metrics from output
        answer = ""
        metrics = {}
        
        lines = result.stdout.split('\n')
        in_answer = False
        answer_lines = []
        
        for line in lines:
            if "================== ANSWER ==================" in line:
                in_answer = True
                continue
            if "----------------- METRICS ------------------" in line:
                in_answer = False
                continue
            if in_answer and line.strip():
                answer_lines.append(line)
            
            # Extract metrics
            if "docs_used=" in line:
                # Parse: - collection: docs_used=2, avg_sim=0.659, strong_share=0.00, time_ms=10582, conf=0.48
                match = re.search(r'docs_used=(\d+)', line)
                if match:
                    if 'docs_used' not in metrics:
                        metrics['docs_used'] = []
                    metrics['docs_used'].append(int(match.group(1)))
                
                match = re.search(r'avg_sim=([\d.]+)', line)
                if match:
                    if 'avg_sim' not in metrics:
                        metrics['avg_sim'] = []
                    metrics['avg_sim'].append(float(match.group(1)))
                
                match = re.search(r'strong_share=([\d.]+)', line)
                if match:
                    if 'strong_share' not in metrics:
                        metrics['strong_share'] = []
                    metrics['strong_share'].append(float(match.group(1)))
        
        answer = '\n'.join(answer_lines).strip()
        
        return answer, rewritten, metrics, latency_ms
    
    def evaluate_keyword_match(self, answer: str, expected_keywords: List[str]) -> Tuple[float, List[str]]:
        """Check if expected keywords appear in the answer."""
        answer_lower = answer.lower()
        found = [kw for kw in expected_keywords if kw.lower() in answer_lower]
        score = len(found) / len(expected_keywords) if expected_keywords else 1.0
        return score, found
    
    def evaluate_context_rewrite(self, rewritten: str, should_contain: List[str] = None, 
                                 should_not_contain: List[str] = None) -> bool:
        """Check if context rewriting is correct."""
        rewritten_lower = rewritten.lower()
        
        if should_contain:
            for keyword in should_contain:
                if keyword.lower() not in rewritten_lower:
                    print(f"      ✗ Missing expected keyword: '{keyword}'")
                    return False
        
        if should_not_contain:
            for keyword in should_not_contain:
                if keyword.lower() in rewritten_lower:
                    print(f"      ✗ Contains forbidden keyword: '{keyword}'")
                    return False
        
        return True
    
    def run_single_turn_evaluation(self, test_data: Dict[str, Any]) -> List[EvaluationResult]:
        """Run evaluation on single-turn queries."""
        print("\n" + "="*80)
        print("SINGLE-TURN QUERY EVALUATION")
        print("="*80)
        
        # Clear session for fresh start
        if os.path.exists(self.session_file):
            os.remove(self.session_file)
        
        results = []
        queries = test_data.get("single_turn_queries", [])
        
        for i, test_case in enumerate(queries, 1):
            query = test_case["query"]
            expected_keywords = test_case.get("expected_keywords", [])
            
            print(f"\n[{i}/{len(queries)}] {query}")
            
            answer, rewritten, metrics, latency = self.run_query(query)
            
            # Aggregate metrics
            avg_sim = mean(metrics.get('avg_sim', [0.0]))
            strong_share = mean(metrics.get('strong_share', [0.0]))
            docs_used = sum(metrics.get('docs_used', [0]))
            
            # Keyword Match
            kw_score, found_kw = self.evaluate_keyword_match(answer, expected_keywords)
            
            result = EvaluationResult(
                query=query,
                answer=answer[:200] + "..." if len(answer) > 200 else answer,
                avg_similarity=avg_sim,
                strong_share=strong_share,
                docs_used=docs_used,
                latency_ms=latency,
                keyword_match_score=kw_score,
                expected_keywords=expected_keywords,
                found_keywords=found_kw
            )
            results.append(result)
            
            print(f"  ✓ Latency: {latency}ms")
            print(f"  ✓ Retrieval: avg_sim={avg_sim:.3f}, strong_share={strong_share:.2f}, docs={docs_used}")
            print(f"  ✓ Keywords: {kw_score:.1%} ({len(found_kw)}/{len(expected_keywords)}) - {found_kw}")
        
        return results
    
    def run_conversational_evaluation(self, test_data: Dict[str, Any]) -> List[EvaluationResult]:
        """Run evaluation on conversational flows."""
        print("\n" + "="*80)
        print("CONVERSATIONAL FLOW EVALUATION")
        print("="*80)
        
        results = []
        flows = test_data.get("conversational_flows", [])
        
        for flow in flows:
            flow_name = flow["name"]
            print(f"\n{flow_name}")
            print("-" * 80)
            
            # Clear session for each flow
            if os.path.exists(self.session_file):
                os.remove(self.session_file)
            
            for i, test_case in enumerate(flow["queries"], 1):
                query = test_case["query"]
                should_contain = test_case.get("should_contain", [])
                should_not_contain = test_case.get("should_not_contain", [])
                
                print(f"\n  Q{i}: {query}")
                
                answer, rewritten, metrics, latency = self.run_query(query)
                
                # Check if rewrite happened
                if rewritten != query:
                    print(f"    → Rewritten: {rewritten}")
                
                # Aggregate metrics
                avg_sim = mean(metrics.get('avg_sim', [0.0]))
                strong_share = mean(metrics.get('strong_share', [0.0]))
                docs_used = sum(metrics.get('docs_used', [0]))
                
                # Check context rewriting
                context_correct = self.evaluate_context_rewrite(rewritten, should_contain, should_not_contain)
                
                if context_correct:
                    print(f"    ✓ Context rewrite correct")
                
                result = EvaluationResult(
                    query=query,
                    answer=answer[:100] + "..." if len(answer) > 100 else answer,
                    rewritten_query=rewritten,
                    avg_similarity=avg_sim,
                    strong_share=strong_share,
                    docs_used=docs_used,
                    latency_ms=latency,
                    context_rewrite_correct=context_correct
                )
                results.append(result)
                
                print(f"    ✓ Latency: {latency}ms, Docs: {docs_used}, Avg Sim: {avg_sim:.3f}")
        
        return results
    
    def generate_report(self, single_results: List[EvaluationResult], 
                       conv_results: List[EvaluationResult]) -> str:
        """Generate a comprehensive evaluation report."""
        report = []
        report.append("\n" + "="*80)
        report.append("RAG SYSTEM EVALUATION REPORT")
        report.append("="*80)
        report.append("")
        
        all_results = single_results + conv_results
        
        # 1. Retrieval Quality
        report.append("1. RETRIEVAL QUALITY")
        report.append("-" * 40)
        avg_sims = [r.avg_similarity for r in all_results if r.avg_similarity > 0]
        strong_shares = [r.strong_share for r in all_results if r.strong_share > 0]
        docs_counts = [r.docs_used for r in all_results if r.docs_used > 0]
        
        if avg_sims:
            report.append(f"  Average Similarity: {mean(avg_sims):.3f} (±{stdev(avg_sims) if len(avg_sims) > 1 else 0:.3f})")
            report.append(f"  Range: [{min(avg_sims):.3f}, {max(avg_sims):.3f}]")
        if strong_shares:
            report.append(f"  Strong Share: {mean(strong_shares):.3f} (±{stdev(strong_shares) if len(strong_shares) > 1 else 0:.3f})")
        if docs_counts:
            report.append(f"  Docs Retrieved: {mean(docs_counts):.1f} (±{stdev(docs_counts) if len(docs_counts) > 1 else 0:.1f})")
        report.append("")
        
        # 2. Conversational Context
        report.append("2. CONVERSATIONAL CONTEXT")
        report.append("-" * 40)
        if conv_results:
            context_correct = sum(1 for r in conv_results if r.context_rewrite_correct)
            report.append(f"  Context Rewrite Accuracy: {context_correct}/{len(conv_results)} ({context_correct/len(conv_results)*100:.1f}%)")
            
            rewrites = [r for r in conv_results if r.rewritten_query != r.query]
            report.append(f"  Queries Rewritten: {len(rewrites)}/{len(conv_results)}")
        else:
            report.append("  No conversational tests run")
        report.append("")
        
        # 3. Performance
        report.append("3. SYSTEM PERFORMANCE")
        report.append("-" * 40)
        latencies = [r.latency_ms for r in all_results if r.latency_ms > 0]
        if latencies:
            report.append(f"  Average Latency: {mean(latencies):.0f}ms (±{stdev(latencies) if len(latencies) > 1 else 0:.0f}ms)")
            report.append(f"  Min Latency: {min(latencies)}ms")
            report.append(f"  Max Latency: {max(latencies)}ms")
            report.append(f"  Total Queries: {len(all_results)}")
        report.append("")
        
        # 4. Ground Truth (Keyword Matching)
        report.append("4. KEYWORD MATCHING (Ground Truth)")
        report.append("-" * 40)
        kw_scores = [r.keyword_match_score for r in single_results if r.expected_keywords]
        if kw_scores:
            report.append(f"  Average Keyword Match: {mean(kw_scores):.1%}")
            perfect_matches = sum(1 for s in kw_scores if s == 1.0)
            report.append(f"  Perfect Matches: {perfect_matches}/{len(kw_scores)}")
            
            # Show keyword details
            report.append("\n  Keyword Details:")
            for r in single_results:
                if r.expected_keywords:
                    report.append(f"    - {r.query[:50]}...")
                    report.append(f"      Found: {len(r.found_keywords)}/{len(r.expected_keywords)} - {r.found_keywords}")
        report.append("")
        
        # Overall Health Score
        report.append("="*80)
        report.append("OVERALL HEALTH SCORE")
        report.append("="*80)
        
        health_components = []
        if avg_sims:
            health_components.append(("Retrieval Quality (Avg Sim)", mean(avg_sims)))
        if kw_scores:
            health_components.append(("Keyword Match", mean(kw_scores)))
        if conv_results:
            context_acc = sum(1 for r in conv_results if r.context_rewrite_correct) / len(conv_results)
            health_components.append(("Context Accuracy", context_acc))
        
        if health_components:
            overall_score = mean([score for _, score in health_components])
            report.append(f"\n  Overall Score: {overall_score:.2f} / 1.00")
            report.append("\n  Component Scores:")
            for name, score in health_components:
                bar_length = int(score * 40)
                bar = "█" * bar_length + "░" * (40 - bar_length)
                report.append(f"    {name:.<35} {score:.2f} {bar}")
        
        report.append("\n" + "="*80)
        
        return "\n".join(report)


def main():
    """Main evaluation function."""
    print("Starting RAG System Evaluation...")
    
    # Load test dataset
    try:
        with open("evaluation_dataset.json", "r") as f:
            test_data = json.load(f)
    except FileNotFoundError:
        print("Error: evaluation_dataset.json not found!")
        return
    
    evaluator = RAGEvaluator()
    
    # Run evaluations
    single_results = evaluator.run_single_turn_evaluation(test_data)
    conv_results = evaluator.run_conversational_evaluation(test_data)
    
    # Generate report
    report = evaluator.generate_report(single_results, conv_results)
    
    # Print report
    print(report)
    
    # Save report
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    report_file = f"evaluation_report_{timestamp}.txt"
    with open(report_file, "w") as f:
        f.write(report)
    
    # Save detailed results as JSON
    results_file = f"evaluation_results_{timestamp}.json"
    all_results = {
        "single_turn": [asdict(r) for r in single_results],
        "conversational": [asdict(r) for r in conv_results],
        "timestamp": timestamp
    }
    with open(results_file, "w") as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n✓ Report saved to: {report_file}")
    print(f"✓ Detailed results saved to: {results_file}")


if __name__ == "__main__":
    main()
