# Milestone 6 Benchmark Report

Generated: 2026-11-15T21:27:52.124607+00:00

## Workload
- Distinct complex prompts: 24
- Cold runs: 24
- Warm-cache runs: 24

## Cold Performance
- Throughput: 0.0509 QPS
- Citation pass rate: 83.3%
- Provenance pass rate: 83.3%
- End-to-end P50: 20854.06 ms
- End-to-end P95: 27691.83 ms
- End-to-end P99: 28437.04 ms

## Stage Latency
```json
{
  "sql_ms": {
    "count": 8,
    "mean_ms": 123.29,
    "p50_ms": 14.17,
    "p95_ms": 491.2,
    "p99_ms": 539.1,
    "min_ms": 0.01,
    "max_ms": 551.07
  },
  "mongo_ms": {
    "count": 24,
    "mean_ms": 14.15,
    "p50_ms": 1.79,
    "p95_ms": 90.66,
    "p99_ms": 155.8,
    "min_ms": 0.9,
    "max_ms": 171.54
  },
  "vector_ms": {
    "count": 24,
    "mean_ms": 74.1,
    "p50_ms": 32.6,
    "p95_ms": 348.65,
    "p99_ms": 464.4,
    "min_ms": 25.58,
    "max_ms": 488.94
  },
  "retrieval_total_ms": {
    "count": 24,
    "mean_ms": 129.54,
    "p50_ms": 34.86,
    "p95_ms": 635.45,
    "p99_ms": 713.68,
    "min_ms": 27.5,
    "max_ms": 729.44
  },
  "llm_ms": {
    "count": 24,
    "mean_ms": 19510.55,
    "p50_ms": 20823.4,
    "p95_ms": 27549.69,
    "p99_ms": 27917.35,
    "min_ms": 826.28,
    "max_ms": 27941.02
  },
  "total_ms": {
    "count": 24,
    "mean_ms": 19640.43,
    "p50_ms": 20854.06,
    "p95_ms": 27691.83,
    "p99_ms": 28437.04,
    "min_ms": 1261.14,
    "max_ms": 28567.68
  }
}
```

## Cache Optimization
The optimized pass repeats the same 24 questions using a bounded in-memory response cache.
This demonstrates caching without adding infrastructure outside the assignment.

- Warm-cache P50: 0.1 ms
- Warm-cache throughput: 1115.1934 QPS
- Warm-cache citation pass rate: 83.3%
- Warm-cache provenance pass rate: 83.3%
