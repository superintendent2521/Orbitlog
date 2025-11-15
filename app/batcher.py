from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from .database import AsyncSessionLocal
from . import models


@dataclass(slots=True)
class _QueuedLog:
    workspace_id: str
    message: str
    code: int
    meta: dict[str, Any] | None
    future: asyncio.Future[models.LogEntry]


class LogBatcher:
    """Buffers log entries and flushes them to the DB in batches."""

    def __init__(self, *, max_batch_size: int, flush_interval: float) -> None:
        self._queue: asyncio.Queue[_QueuedLog | None] = asyncio.Queue()
        self._max_batch_size = max_batch_size
        self._flush_interval = flush_interval
        self._task: asyncio.Task[None] | None = None

    def start(self) -> None:
        if self._task is None:
            self._task = asyncio.create_task(self._run())

    async def stop(self) -> None:
        if self._task is None:
            return
        await self._queue.join()
        await self._queue.put(None)
        await self._task
        self._task = None

    async def enqueue(
        self,
        *,
        workspace_id: str,
        message: str,
        code: int,
        meta: dict[str, Any] | None,
    ) -> models.LogEntry:
        loop = asyncio.get_running_loop()
        future: asyncio.Future[models.LogEntry] = loop.create_future()
        await self._queue.put(
            _QueuedLog(
                workspace_id=workspace_id,
                message=message,
                code=code,
                meta=meta,
                future=future,
            )
        )
        return await future

    async def _run(self) -> None:
        while True:
            item = await self._queue.get()
            if item is None:
                self._queue.task_done()
                break

            batch: list[_QueuedLog] = [item]
            start = asyncio.get_running_loop().time()
            while len(batch) < self._max_batch_size:
                timeout = self._flush_interval - (asyncio.get_running_loop().time() - start)
                if timeout <= 0:
                    break
                try:
                    next_item = await asyncio.wait_for(self._queue.get(), timeout=timeout)
                except asyncio.TimeoutError:
                    break
                if next_item is None:
                    # Sentinel encountered; finish current batch then requeue for shutdown.
                    self._queue.task_done()
                    await self._queue.put(None)
                    break
                batch.append(next_item)

            await self._flush(batch)
            for _ in batch:
                self._queue.task_done()

    async def _flush(self, batch: list[_QueuedLog]) -> None:
        if not batch:
            return

        entries = [
            models.LogEntry(
                workspace_id=item.workspace_id,
                message=item.message,
                code=item.code,
                meta=item.meta,
                created_at=datetime.now(timezone.utc),
            )
            for item in batch
        ]
        try:
            async with AsyncSessionLocal() as session:
                session.add_all(entries)
                await session.commit()
        except Exception as exc:  # noqa: BLE001 - bubble error to waiting callers
            for item in batch:
                if not item.future.done():
                    item.future.set_exception(exc)
            return

        for entry, item in zip(entries, batch):
            if not item.future.done():
                item.future.set_result(entry)
