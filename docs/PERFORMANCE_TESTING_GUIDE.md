# Performance Testing Guide

## Overview

The `performance_test_extensive.py` script provides comprehensive performance testing for the Agentic RAG system.

## Test Suite Components

### 1. Stress Testing
**Purpose**: Measure system behavior under sustained load.

**Test Parameters**:
- 20 unique queries
- 3 iterations each
- Total: 60 queries executed sequentially

**Metrics Collected**:
- **Latency Statistics**:
  - Average, Median, P95, P99
  - Min, Max
- **Throughput**: Queries per second
- **Resource Usage**:
  - Memory consumption (MB)
  - CPU utilization (%)
- **Success Rate**: Percentage of successful queries

**Expected Results** (Based on current system):
- Avg Latency: ~28-30 seconds
- Throughput: ~0.03-0.04 queries/second
- Success Rate: >95%

### 2. Concurrency Testing
**Purpose**: Test parallel query execution capabilities.

**Test Parameters**:
- 10 queries
- 3 concurrent workers
- ThreadPoolExecutor for parallelization

**Metrics Collected**:
- Total execution time
- Average latency per query
- Throughput (queries/second)
- Speedup vs sequential execution

**Expected Results**:
- Speedup: ~2-2.5x (due to I/O-bound operations)
- Throughput: ~0.08-0.10 queries/second

### 3. Latency Breakdown Analysis
**Purpose**: Identify performance bottlenecks.

**Test Parameters**:
- Single query: "What are the signs of diabetes?"
- Detailed timing of each agent

**Metrics Collected**:
- Total latency
- Per-agent execution time
- Number of agents invoked
- Orchestration overhead

**Expected Breakdown**:
- Agent execution: ~80-85% of total time
- Orchestration overhead: ~15-20%

## How to Run

```bash
python3 performance_test_extensive.py
```

## Interpreting Results

### Stress Test Results

```
Total Queries: 60
Successful: 58
Failed: 2
Success Rate: 96.7%

Latency Statistics:
  Average: 28500ms
  Median: 27800ms
  P95: 35000ms
  P99: 40000ms
  Min: 18000ms
  Max: 42000ms

Throughput:
  Total Time: 1710.5s
  Queries/Second: 0.034

Resource Usage:
  Avg Memory Delta: 15.2MB
  Peak Memory Delta: 45.8MB
  Avg CPU: 25.3%
```

**Analysis**:
- **High P95/P99**: Indicates occasional slow queries (likely complex topics)
- **Low Throughput**: Expected for sequential execution
- **Memory Delta**: Shows memory is released between queries (no leaks)

### Concurrency Test Results

```
Total Queries: 10
Successful: 10
Total Time: 95.3s
Avg Latency: 28200ms
Throughput: 0.105 queries/second
Speedup vs Sequential: 2.96x
```

**Analysis**:
- **Speedup ~3x**: Good parallelization efficiency with 3 workers
- **Throughput 3x higher**: Confirms concurrency benefits

### Latency Breakdown

```
Total Latency: 30500ms
Number of Agents: 3
Avg Agent Time: 8500ms
Agent Times: [9200ms, 8100ms, 8200ms]
Orchestration Overhead: 5000ms
```

**Analysis**:
- **Agent Time**: ~83% of total (25500ms / 30500ms)
- **Overhead**: ~16% (orchestration, LLM calls, merging)

## Performance Optimization Recommendations

Based on test results:

### If Latency is High (>35s avg)
1. **Reduce AGENT_MAX_ITERS**: From 2 to 1
2. **Implement Caching**: Cache common queries
3. **Optimize Thresholds**: Further tune X0, Y0

### If Memory Usage is High (>100MB delta)
1. **Check for Memory Leaks**: Monitor across iterations
2. **Limit Document Count**: Reduce reranker top-k
3. **Clear Session Files**: Delete old session files

### If Throughput is Low (<0.03 qps)
1. **Use Concurrency**: Process queries in parallel
2. **Async Processing**: Implement async/await patterns
3. **Batch Processing**: Group similar queries

## Continuous Monitoring

Run this test suite:
- **After each optimization**: To measure impact
- **Before deployment**: To establish baseline
- **Weekly**: To detect performance degradation

## Output Files

The script generates:
- `performance_test_results_YYYYMMDD_HHMMSS.json`: Detailed metrics
- `stress_test_iter*.json`: Session files (can be deleted)
- `concurrent_*.json`: Session files (can be deleted)

## Cleanup

```bash
# Remove session files
rm stress_test_iter*.json concurrent_*.json perf_test_session.json
```
