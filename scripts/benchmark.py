from __future__ import annotations

import argparse
import asyncio
import math
import os
import random
import string
from statistics import mean
from time import perf_counter

import httpx
from rich.console import Console
from rich.table import Table

DEFAULT_WORKSPACE = "1234567890123456"
console = Console()


def _random_message(size: int) -> str:
    alphabet = string.ascii_letters + string.digits + " "
    return "".join(random.choice(alphabet) for _ in range(size))


async def _send_request(
    client: httpx.AsyncClient,
    workspace_id: str,
    message_size: int,
) -> tuple[float, bool]:
    payload = {
        "message": _random_message(message_size),
        "code": random.choice([200, 300, 400, 500]),
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


async def run_benchmark(
    *,
    url: str,
    workspace_id: str,
    total_requests: int,
    concurrency: int,
    message_size: int,
    inprocess: bool,
) -> dict[str, float]:
    latencies: list[float] = []
    successes = 0
    sem = asyncio.Semaphore(concurrency)

    transport: httpx.AsyncBaseTransport | None = None
    base_url = url
    lifespan_cm = None
    if inprocess:
        os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///./bench.db")
        from app.main import app  # Import lazily so env vars take effect

        transport = httpx.ASGITransport(app=app)
        base_url = "http://inprocess"
        lifespan_cm = app.router.lifespan_context(app)

    async def _run_client() -> float:
        async with httpx.AsyncClient(base_url=base_url, timeout=30.0, transport=transport) as client:
            async def worker() -> None:
                nonlocal successes
                async with sem:
                    latency, ok = await _send_request(client, workspace_id, message_size)
                    latencies.append(latency)
                    if ok:
                        successes += 1

            start = perf_counter()
            await asyncio.gather(*[asyncio.create_task(worker()) for _ in range(total_requests)])
            return perf_counter() - start

    if lifespan_cm is not None:
        async with lifespan_cm:
            duration = await _run_client()
    else:
        duration = await _run_client()

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
    parser = argparse.ArgumentParser(description="Simple async benchmark for Orbital Log API")
    parser.add_argument("--url", default="http://127.0.0.1:8000", help="FastAPI base URL")
    parser.add_argument("--workspace", default=DEFAULT_WORKSPACE, help="Workspace id to use")
    parser.add_argument("--requests", type=int, default=200, help="Total number of requests")
    parser.add_argument("--concurrency", type=int, default=20, help="Concurrent workers")
    parser.add_argument("--message-size", type=int, default=120, help="Message length in characters")
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

    workspace = args.workspace or DEFAULT_WORKSPACE
    console.print(f"Running benchmark against {args.url} workspace={workspace}")
    results = asyncio.run(
        run_benchmark(
            url=args.url,
            workspace_id=workspace,
            total_requests=args.requests,
            concurrency=args.concurrency,
            message_size=args.message_size,
            inprocess=args.inprocess,
        )
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
