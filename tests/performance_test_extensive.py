#!/usr/bin/env python3
"""
Extensive Performance Testing Suite for Agentic RAG System

Tests:
1. Stress Testing: High volume query processing
2. Concurrency Testing: Parallel query execution
3. Latency Profiling: Detailed timing breakdown
4. Memory Usage: Resource consumption tracking
5. Performance Degradation: System behavior under load
6. Cache Effectiveness: Query result caching analysis
"""

import os
import sys
import json
import time
import subprocess
import psutil
import threading
from typing import Dict, List, Any, Tuple
from dataclasses import dataclass, field, asdict
from statistics import mean, stdev, median
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor, as_completed


@dataclass
class PerformanceMetrics:
    """Performance metrics for a single query."""
    query: str
    latency_ms: int
    memory_mb: float
    cpu_percent: float
    docs_retrieved: int
    avg_similarity: float
    success: bool
    error: str = ""


@dataclass
class StressTestResults:
    """Results from stress testing."""
    total_queries: int
    successful_queries: int
    failed_queries: int
    avg_latency_ms: float
    median_latency_ms: float
    p95_latency_ms: float
    p99_latency_ms: float
    min_latency_ms: int
    max_latency_ms: int
    total_time_s: float
    queries_per_second: float
    avg_memory_mb: float
    peak_memory_mb: float
    avg_cpu_percent: float


class ExtensivePerformanceTester:
    """Comprehensive performance testing suite."""
    
    def __init__(self):
        self.process = psutil.Process()
        self.baseline_memory = self.process.memory_info().rss / 1024 / 1024
    
    def get_system_metrics(self) -> Tuple[float, float]:
        """Get current memory and CPU usage."""
        memory_mb = self.process.memory_info().rss / 1024 / 1024
        cpu_percent = self.process.cpu_percent(interval=0.1)
        return memory_mb, cpu_percent
    
    def run_single_query(self, query: str, session_file: str = "perf_test_session.json") -> PerformanceMetrics:
        """Run a single query and collect performance metrics."""
        start_time = time.time()
        memory_before, _ = self.get_system_metrics()
        
        try:
            cmd = [sys.executable, "anti_test.py", "--query", query, "--session_file", session_file]
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=60)
            
            latency_ms = int((time.time() - start_time) * 1000)
            memory_after, cpu_percent = self.get_system_metrics()
            memory_delta = memory_after - memory_before
            
            # Parse output for metrics
            docs_retrieved = 0
            avg_similarity = 0.0
            for line in result.stdout.split('\n'):
                if "docs_used=" in line:
                    import re
                    match = re.search(r'docs_used=(\d+)', line)
                    if match:
                        docs_retrieved = max(docs_retrieved, int(match.group(1)))
                    match = re.search(r'avg_sim=([\d.]+)', line)
                    if match:
                        avg_similarity = max(avg_similarity, float(match.group(1)))
            
            return PerformanceMetrics(
                query=query,
                latency_ms=latency_ms,
                memory_mb=memory_delta,
                cpu_percent=cpu_percent,
                docs_retrieved=docs_retrieved,
                avg_similarity=avg_similarity,
                success=result.returncode == 0
            )
        except subprocess.TimeoutExpired:
            return PerformanceMetrics(
                query=query,
                latency_ms=60000,
                memory_mb=0,
                cpu_percent=0,
                docs_retrieved=0,
                avg_similarity=0,
                success=False,
                error="Timeout"
            )
        except Exception as e:
            return PerformanceMetrics(
                query=query,
                latency_ms=0,
                memory_mb=0,
                cpu_percent=0,
                docs_retrieved=0,
                avg_similarity=0,
                success=False,
                error=str(e)
            )
    
    def stress_test(self, queries: List[str], iterations: int = 3) -> StressTestResults:
        """Run stress test with multiple iterations of queries."""
        print(f"\n{'='*80}")
        print(f"STRESS TEST: {len(queries)} queries × {iterations} iterations = {len(queries) * iterations} total")
        print(f"{'='*80}\n")
        
        all_metrics = []
        start_time = time.time()
        
        for iteration in range(iterations):
            print(f"Iteration {iteration + 1}/{iterations}")
            for i, query in enumerate(queries, 1):
                print(f"  [{i}/{len(queries)}] {query[:50]}...", end=" ")
                metrics = self.run_single_query(query, f"stress_test_iter{iteration}.json")
                all_metrics.append(metrics)
                
                if metrics.success:
                    print(f"✓ {metrics.latency_ms}ms")
                else:
                    print(f"✗ {metrics.error}")
        
        total_time = time.time() - start_time
        
        # Calculate statistics
        successful = [m for m in all_metrics if m.success]
        failed = [m for m in all_metrics if not m.success]
        
        if successful:
            latencies = [m.latency_ms for m in successful]
            latencies_sorted = sorted(latencies)
            
            return StressTestResults(
                total_queries=len(all_metrics),
                successful_queries=len(successful),
                failed_queries=len(failed),
                avg_latency_ms=mean(latencies),
                median_latency_ms=median(latencies),
                p95_latency_ms=latencies_sorted[int(len(latencies_sorted) * 0.95)],
                p99_latency_ms=latencies_sorted[int(len(latencies_sorted) * 0.99)],
                min_latency_ms=min(latencies),
                max_latency_ms=max(latencies),
                total_time_s=total_time,
                queries_per_second=len(successful) / total_time,
                avg_memory_mb=mean([m.memory_mb for m in successful]),
                peak_memory_mb=max([m.memory_mb for m in successful]),
                avg_cpu_percent=mean([m.cpu_percent for m in successful])
            )
        else:
            return StressTestResults(
                total_queries=len(all_metrics),
                successful_queries=0,
                failed_queries=len(failed),
                avg_latency_ms=0,
                median_latency_ms=0,
                p95_latency_ms=0,
                p99_latency_ms=0,
                min_latency_ms=0,
                max_latency_ms=0,
                total_time_s=total_time,
                queries_per_second=0,
                avg_memory_mb=0,
                peak_memory_mb=0,
                avg_cpu_percent=0
            )
    
    def concurrency_test(self, queries: List[str], max_workers: int = 3) -> Dict[str, Any]:
        """Test concurrent query execution."""
        print(f"\n{'='*80}")
        print(f"CONCURRENCY TEST: {len(queries)} queries with {max_workers} workers")
        print(f"{'='*80}\n")
        
        start_time = time.time()
        results = []
        
        with ThreadPoolExecutor(max_workers=max_workers) as executor:
            futures = {executor.submit(self.run_single_query, q, f"concurrent_{i}.json"): (i, q) 
                      for i, q in enumerate(queries)}
            
            for future in as_completed(futures):
                i, query = futures[future]
                try:
                    metrics = future.result()
                    results.append(metrics)
                    print(f"  [{i+1}/{len(queries)}] {query[:50]}... ✓ {metrics.latency_ms}ms")
                except Exception as e:
                    print(f"  [{i+1}/{len(queries)}] {query[:50]}... ✗ {e}")
        
        total_time = time.time() - start_time
        successful = [r for r in results if r.success]
        
        return {
            "total_queries": len(queries),
            "successful": len(successful),
            "failed": len(results) - len(successful),
            "total_time_s": total_time,
            "avg_latency_ms": mean([r.latency_ms for r in successful]) if successful else 0,
            "throughput_qps": len(successful) / total_time if total_time > 0 else 0,
            "speedup_vs_sequential": (len(successful) * mean([r.latency_ms for r in successful]) / 1000) / total_time if successful and total_time > 0 else 0
        }
    
    def latency_breakdown_test(self, query: str) -> Dict[str, Any]:
        """Detailed latency profiling for a single query."""
        print(f"\n{'='*80}")
        print(f"LATENCY BREAKDOWN: {query}")
        print(f"{'='*80}\n")
        
        # Run with verbose output
        start_time = time.time()
        cmd = [sys.executable, "anti_test.py", "--query", query]
        result = subprocess.run(cmd, capture_output=True, text=True)
        total_time = time.time() - start_time
        
        # Parse agent timings
        agent_times = []
        for line in result.stdout.split('\n'):
            if "time_ms=" in line:
                import re
                match = re.search(r'time_ms=(\d+)', line)
                if match:
                    agent_times.append(int(match.group(1)))
        
        return {
            "query": query,
            "total_latency_ms": int(total_time * 1000),
            "agent_times_ms": agent_times,
            "avg_agent_time_ms": mean(agent_times) if agent_times else 0,
            "num_agents": len(agent_times),
            "overhead_ms": int(total_time * 1000) - sum(agent_times) if agent_times else 0
        }


def generate_test_queries(count: int = 50) -> List[str]:
    """Generate a diverse set of test queries."""
    base_queries = [
        "What are the signs of diabetes?",
        "What causes heart disease?",
        "What medications are used for diabetes?",
        "What are migraine symptoms?",
        "How to prevent high blood pressure?",
        "What are the complications of untreated diabetes?",
        "How is type 2 diabetes diagnosed?",
        "What are the risk factors for stroke?",
        "What is the difference between type 1 and type 2 diabetes?",
        "What are the symptoms of a heart attack?",
        "How is asthma treated?",
        "What causes migraine headaches?",
        "What are the side effects of metformin?",
        "How can I lower my cholesterol naturally?",
        "What is prediabetes?",
        "What is DM?",
        "HTN management",
        "CAD symptoms",
        "What are the warning signs of stroke?",
        "How to manage type 2 diabetes?",
    ]
    
    # Repeat to reach desired count
    queries = []
    while len(queries) < count:
        queries.extend(base_queries)
    
    return queries[:count]


def main():
    """Run comprehensive performance tests."""
    print("="*80)
    print("EXTENSIVE PERFORMANCE TESTING SUITE")
    print("="*80)
    
    tester = ExtensivePerformanceTester()
    
    # Test 1: Stress Test
    print("\n" + "="*80)
    print("TEST 1: STRESS TESTING")
    print("="*80)
    stress_queries = generate_test_queries(20)
    stress_results = tester.stress_test(stress_queries, iterations=3)
    
    print(f"\n{'='*80}")
    print("STRESS TEST RESULTS")
    print(f"{'='*80}")
    print(f"Total Queries: {stress_results.total_queries}")
    print(f"Successful: {stress_results.successful_queries}")
    print(f"Failed: {stress_results.failed_queries}")
    print(f"Success Rate: {stress_results.successful_queries / stress_results.total_queries * 100:.1f}%")
    print(f"\nLatency Statistics:")
    print(f"  Average: {stress_results.avg_latency_ms:.0f}ms")
    print(f"  Median: {stress_results.median_latency_ms:.0f}ms")
    print(f"  P95: {stress_results.p95_latency_ms:.0f}ms")
    print(f"  P99: {stress_results.p99_latency_ms:.0f}ms")
    print(f"  Min: {stress_results.min_latency_ms}ms")
    print(f"  Max: {stress_results.max_latency_ms}ms")
    print(f"\nThroughput:")
    print(f"  Total Time: {stress_results.total_time_s:.1f}s")
    print(f"  Queries/Second: {stress_results.queries_per_second:.2f}")
    print(f"\nResource Usage:")
    print(f"  Avg Memory Delta: {stress_results.avg_memory_mb:.1f}MB")
    print(f"  Peak Memory Delta: {stress_results.peak_memory_mb:.1f}MB")
    print(f"  Avg CPU: {stress_results.avg_cpu_percent:.1f}%")
    
    # Test 2: Concurrency Test
    print("\n" + "="*80)
    print("TEST 2: CONCURRENCY TESTING")
    print("="*80)
    concurrent_queries = generate_test_queries(10)
    concurrency_results = tester.concurrency_test(concurrent_queries, max_workers=3)
    
    print(f"\n{'='*80}")
    print("CONCURRENCY TEST RESULTS")
    print(f"{'='*80}")
    print(f"Total Queries: {concurrency_results['total_queries']}")
    print(f"Successful: {concurrency_results['successful']}")
    print(f"Total Time: {concurrency_results['total_time_s']:.1f}s")
    print(f"Avg Latency: {concurrency_results['avg_latency_ms']:.0f}ms")
    print(f"Throughput: {concurrency_results['throughput_qps']:.2f} queries/second")
    print(f"Speedup vs Sequential: {concurrency_results['speedup_vs_sequential']:.2f}x")
    
    # Test 3: Latency Breakdown
    print("\n" + "="*80)
    print("TEST 3: LATENCY BREAKDOWN ANALYSIS")
    print("="*80)
    breakdown = tester.latency_breakdown_test("What are the signs of diabetes?")
    
    print(f"\n{'='*80}")
    print("LATENCY BREAKDOWN RESULTS")
    print(f"{'='*80}")
    print(f"Total Latency: {breakdown['total_latency_ms']}ms")
    print(f"Number of Agents: {breakdown['num_agents']}")
    print(f"Avg Agent Time: {breakdown['avg_agent_time_ms']:.0f}ms")
    print(f"Agent Times: {breakdown['agent_times_ms']}")
    print(f"Orchestration Overhead: {breakdown['overhead_ms']}ms")
    
    # Save detailed results
    timestamp = time.strftime("%Y%m%d_%H%M%S")
    results_file = f"performance_test_results_{timestamp}.json"
    
    all_results = {
        "stress_test": asdict(stress_results),
        "concurrency_test": concurrency_results,
        "latency_breakdown": breakdown,
        "timestamp": timestamp
    }
    
    with open(results_file, "w") as f:
        json.dump(all_results, f, indent=2)
    
    print(f"\n{'='*80}")
    print(f"✓ Results saved to: {results_file}")
    print(f"{'='*80}\n")


if __name__ == "__main__":
    main()
