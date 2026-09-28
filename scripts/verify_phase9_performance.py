"""
NWIS Phase 9 — Lightweight Performance & Latency Benchmark
===========================================================
Measures response time, HTTP status, and payload size across
representative operational endpoints.
"""

import time
import json
import urllib.request
import urllib.error

BASE_URL = "http://127.0.0.1:8000"

BENCHMARK_OPERATIONS = [
    {
        "name": "Map Marker Loading",
        "method": "GET",
        "path": "/api/wells/map-markers?include_new=true",
        "payload": None,
    },
    {
        "name": "Well Search & Pagination",
        "method": "GET",
        "path": "/api/wells?offset=0&limit=50",
        "payload": None,
    },
    {
        "name": "Spatial Nearby Wells (25km)",
        "method": "GET",
        "path": "/api/wells/WELL-000050/nearby?radius_km=25",
        "payload": None,
    },
    {
        "name": "Well Intelligence Cockpit",
        "method": "GET",
        "path": "/api/wells/WELL-000050/offset-intelligence",
        "payload": None,
    },
    {
        "name": "Historical Drilling Events",
        "method": "GET",
        "path": "/api/wells/WELL-000050/events",
        "payload": None,
    },
    {
        "name": "ML Drilling Risk Prediction",
        "method": "POST",
        "path": "/api/prediction/risk",
        "payload": {"well_id": "WELL-000050", "depth_md": 3250.0},
    },
    {
        "name": "Document Registry Search",
        "method": "GET",
        "path": "/api/documents?limit=20",
        "payload": None,
    },
    {
        "name": "Grounded Copilot / RAG Query",
        "method": "POST",
        "path": "/api/intelligence/query",
        "payload": {"query": "What are historical kick and loss incidents near WELL-000050?", "well_id": "WELL-000050", "radius_km": 25.0},
    },
    {
        "name": "Dashboard Aggregates",
        "method": "GET",
        "path": "/api/dashboard/stats",
        "payload": None,
    },
    {
        "name": "Live Telemetry Endpoint",
        "method": "GET",
        "path": "/api/live/WELL-000050/telemetry/latest",
        "payload": None,
    },
]


def run_benchmark():
    print("=" * 80)
    print("NWIS PHASE 9 — PERFORMANCE & LATENCY VERIFICATION")
    print("=" * 80)
    print(f"{'Operation':<32} | {'Method':<6} | {'Status':<6} | {'Latency (ms)':<12} | {'Payload (KB)':<12}")
    print("-" * 80)

    results = []

    for op in BENCHMARK_OPERATIONS:
        url = f"{BASE_URL}{op['path']}"
        headers = {"User-Agent": "NWIS-Perf-Runner/1.0", "Accept": "application/json"}
        data = None

        if op["payload"] is not None:
            data = json.dumps(op["payload"]).encode("utf-8")
            headers["Content-Type"] = "application/json"

        req = urllib.request.Request(url, data=data, headers=headers, method=op["method"])

        start_time = time.perf_counter()
        status_code = 0
        payload_size = 0
        error_msg = None

        try:
            with urllib.request.urlopen(req, timeout=15) as resp:
                body = resp.read()
                duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
                status_code = resp.status
                payload_size = len(body)
        except urllib.error.HTTPError as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            status_code = e.code
            error_msg = str(e)
        except Exception as e:
            duration_ms = round((time.perf_counter() - start_time) * 1000.0, 2)
            status_code = 500
            error_msg = str(e)

        payload_kb = round(payload_size / 1024.0, 2)
        print(f"{op['name']:<32} | {op['method']:<6} | {status_code:<6} | {duration_ms:<12.2f} | {payload_kb:<12.2f}")

        results.append({
            "name": op["name"],
            "method": op["method"],
            "path": op["path"],
            "status": status_code,
            "duration_ms": duration_ms,
            "payload_kb": payload_kb,
            "error": error_msg,
        })

    print("-" * 80)
    avg_latency = round(sum(r["duration_ms"] for r in results) / len(results), 2)
    max_latency = round(max(r["duration_ms"] for r in results), 2)
    print(f"Average Latency: {avg_latency} ms | Max Latency: {max_latency} ms")
    print("=" * 80)

    # Save raw results for documentation
    with open("database/phase9_benchmark_results.json", "w", encoding="utf-8") as f:
        json.dump({"results": results, "avg_latency_ms": avg_latency, "max_latency_ms": max_latency}, f, indent=2)

    return results


if __name__ == "__main__":
    run_benchmark()
