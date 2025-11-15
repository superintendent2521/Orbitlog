from __future__ import annotations

import argparse
import asyncio
import math
import os
import random
import string
from concurrent.futures import ThreadPoolExecutor
from statistics import mean
from time import perf_counter

import httpx
from rich.console import Console
from rich.table import Table

DEFAULT_WORKSPACE = "1234567890123456"
console = Console()


def _random_message(size: int, rng: random.Random | None = None) -> str:
    alphabet = string.ascii_letters + string.digits + " "
    generator = rng or random
    return "".join(generator.choice(alphabet) for _ in range(size))


async def _send_request(
    client: httpx.AsyncClient,
    workspace_id: str,
    message_size: int,
    rng: random.Random,
) -> tuple[float, bool]:
    payload = {
        "message": _random_message(message_size, rng),
        "code": rng.choice([200, 300, 400, 500]),
        "meta": {"source": "benchmark"},
    }
    start = perf_counter()
    resp = await client.post(f"/workspaces/{workspace_id}/logs", json=payload)
    latency = perf_counter() - start
    return latency, resp.status_code == 201


def _percentile(numbers: list[float], pct: float) -> float:
    if not numbers:
        return 0.0
    idx = max(0, math.ceil(pct * len(numbers)) - 1)
    return numbers[min(idx, len(numbers) - 1)]


async def _run_worker(
    *,
    base_url: str,
    transport: httpx.AsyncBaseTransport | None,
    workspace_id: str,
    total_requests: int,
    concurrency: int,
    message_size: int,
    timeout: float = 30.0,
) -> tuple[list[float], int]:
    latencies: list[float] = []
    successes = 0
    if total_requests <= 0:
        return latencies, successes

    active_workers = max(1, min(concurrency, total_requests))
    rng = random.Random()
    next_request = 0
    lock = asyncio.Lock()

    async with httpx.AsyncClient(base_url=base_url, timeout=timeout, transport=transport) as client:

        async def worker() -> None:
            nonlocal successes, next_request
            while True:
                async with lock:
                    if next_request >= total_requests:
                        break
                    next_request += 1
                latency, ok = await _send_request(client, workspace_id, message_size, rng)
                latencies.append(latency)
                if ok:
                    successes += 1

        await asyncio.gather(*[asyncio.create_task(worker()) for _ in range(active_workers)])

    return latencies, successes


async def _run_inprocess_worker(
    *,
    workspace_id: str,
    total_requests: int,
    concurrency: int,
    message_size: int,
) -> tuple[list[float], int]:
    os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./bench.db")
    from app.main import app  # Import lazily so env vars take effect

    transport = httpx.ASGITransport(app=app)
    lifespan_cm = app.router.lifespan_context(app)

    async with lifespan_cm:
        return await _run_worker(
            base_url="http://inprocess",
            transport=transport,
            workspace_id=workspace_id,
            total_requests=total_requests,
            concurrency=concurrency,
            message_size=message_size,
        )


def _split_requests(total_requests: int, chunks: int) -> list[int]:
    if chunks <= 0:
        return []
    base = total_requests // chunks
    remainder = total_requests % chunks
    counts: list[int] = []
    for idx in range(chunks):
        count = base + (1 if idx < remainder else 0)
        if count > 0:
            counts.append(count)
    return counts


def _run_http_worker_sync(
    *,
    url: str,
    workspace_id: str,
    requests: int,
    concurrency: int,
    message_size: int,
) -> tuple[list[float], int]:
    async def runner() -> tuple[list[float], int]:
        return await _run_worker(
            base_url=url,
            transport=None,
            workspace_id=workspace_id,
            total_requests=requests,
            concurrency=concurrency,
            message_size=message_size,
        )

    return asyncio.run(runner())


def run_benchmark(
    *,
    url: str,
    workspace_id: str,
    total_requests: int,
    concurrency: int,
    message_size: int,
    inprocess: bool,
    threads: int,
) -> dict[str, float]:
    latencies: list[float] = []
    successes = 0

    if inprocess and threads > 1:
        raise ValueError("Multithreaded benchmarking is not available in --inprocess mode.")

    start = perf_counter()
    if inprocess:
        latencies, successes = asyncio.run(
            _run_inprocess_worker(
                workspace_id=workspace_id,
                total_requests=total_requests,
                concurrency=concurrency,
                message_size=message_size,
            )
        )
        duration = perf_counter() - start
    elif threads <= 1:
        latencies, successes = _run_http_worker_sync(
            url=url,
            workspace_id=workspace_id,
            requests=total_requests,
            concurrency=concurrency,
            message_size=message_size,
        )
        duration = perf_counter() - start
    else:
        request_chunks = _split_requests(total_requests, threads)
        if not request_chunks:
            duration = 0.0
        else:
            with ThreadPoolExecutor(max_workers=len(request_chunks)) as executor:
                futures = [
                    executor.submit(
                        _run_http_worker_sync,
                        url=url,
                        workspace_id=workspace_id,
                        requests=reqs,
                        concurrency=concurrency,
                        message_size=message_size,
                    )
                    for reqs in request_chunks
                ]
                for future in futures:
                    partial_latencies, partial_successes = future.result()
                    latencies.extend(partial_latencies)
                    successes += partial_successes
            duration = perf_counter() - start

    latencies.sort()
    throughput = successes / duration if duration else 0.0
    return {
        "duration": duration,
        "throughput": throughput,
        "successes": successes,
        "mean_latency": mean(latencies) if latencies else 0.0,
        "p95_latency": _percentile(latencies, 0.95),
        "p99_latency": _percentile(latencies, 0.99),
    }


def cli(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Concurrent benchmark driver for Orbital Log API")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="FastAPI base URL")
    parser.add_argument("--workspace", default=DEFAULT_WORKSPACE, help="Workspace id to use")
    parser.add_argument("--requests", type=int, default=200, help="Total number of requests")
    parser.add_argument("--concurrency", type=int, default=20, help="Concurrent workers")
    parser.add_argument("--message-size", type=int, default=120, help="Message length in characters")
    parser.add_argument(
        "--threads",
        type=int,
        default=1,
        help="Number of OS threads to spawn (each thread runs --concurrency async workers)",
    )
    parser.add_argument(
        "--inprocess",
        action="store_true",
        help="Run benchmarks against an in-process ASGI app (uses sqlite bench.db by default)",
    )
    parser.add_argument(
        "--database-url",
        default="sqlite+aiosqlite:///./bench.db",
        help="Database URL when using --inprocess mode",
    )
    args = parser.parse_args(argv)

    if args.inprocess:
        os.environ["DATABASE_URL"] = args.database_url
        console.print(f"Running in-process benchmark with database={args.database_url}")

    if args.threads < 1:
        parser.error("--threads must be >= 1")
    if args.inprocess and args.threads > 1:
        parser.error("--threads > 1 is not supported with --inprocess mode")

    workspace = args.workspace or DEFAULT_WORKSPACE
    console.print(f"Running benchmark against {args.url} workspace={workspace}")
    results = run_benchmark(
        url=args.url,
        workspace_id=workspace,
        total_requests=args.requests,
        concurrency=args.concurrency,
        message_size=args.message_size,
        inprocess=args.inprocess,
        threads=args.threads,
    )
    table = Table(title="Benchmark Results")
    table.add_column("Metric")
    table.add_column("Value")
    for key, value in results.items():
        if key in {"successes"}:
            table.add_row(key, f"{int(value)}")
        else:
            table.add_row(key, f"{value:.4f}")
    console.print(table)


if __name__ == "__main__":
    cli()
