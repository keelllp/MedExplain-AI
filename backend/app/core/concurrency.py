"""Concurrency control for CPU-bound analysis jobs.

The backend runs as a single Uvicorn worker. A BoundedSemaphore(1) serializes
analysis so PaddleOCR (and, later, local LLM inference) never run concurrently on
a laptop CPU — we prefer reliable serialized throughput over contention. Background
analysis runs as a sync task in Starlette's threadpool, so a blocking acquire here
queues additional jobs without stalling the event loop.
"""

from __future__ import annotations

import threading

#: Max concurrent analyses. Intentionally 1 (single-worker, CPU-only laptop).
ANALYSIS_CONCURRENCY = 1

analysis_semaphore = threading.BoundedSemaphore(ANALYSIS_CONCURRENCY)
