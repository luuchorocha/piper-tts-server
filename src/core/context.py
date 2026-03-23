import argparse
import asyncio
from contextlib import asynccontextmanager
from dataclasses import dataclass
from pathlib import Path
from typing import List

from src.managers.voices.manager import VoiceManager


class SynthesisOverloadedError(RuntimeError):
    pass


@dataclass(frozen=True)
class SynthesisCapacitySnapshot:
    limit: int
    in_flight: int
    waiting: int
    max_waiters: int
    acquire_timeout_seconds: float

    @property
    def overloaded(self) -> bool:
        return self.waiting >= self.max_waiters and self.max_waiters >= 0


class SynthesisCapacity:
    def __init__(
        self,
        *,
        limit: int,
        acquire_timeout_seconds: float,
        max_waiters: int,
    ) -> None:
        self.limit = max(1, int(limit))
        self.acquire_timeout_seconds = max(0.1, float(acquire_timeout_seconds))
        self.max_waiters = max(0, int(max_waiters))
        self._semaphore = asyncio.Semaphore(self.limit)
        self._lock = asyncio.Lock()
        self._in_flight = 0
        self._waiting = 0

    @asynccontextmanager
    async def slot(self):
        await self._acquire()
        try:
            yield
        finally:
            await self._release()

    async def snapshot(self) -> SynthesisCapacitySnapshot:
        async with self._lock:
            return SynthesisCapacitySnapshot(
                limit=self.limit,
                in_flight=self._in_flight,
                waiting=self._waiting,
                max_waiters=self.max_waiters,
                acquire_timeout_seconds=self.acquire_timeout_seconds,
            )

    async def _acquire(self) -> None:
        async with self._lock:
            if self._waiting >= self.max_waiters:
                raise SynthesisOverloadedError(
                    "Synthesis capacity is saturated; retry after the current backlog drains.",
                )

            self._waiting += 1

        acquired = False
        try:
            await asyncio.wait_for(
                self._semaphore.acquire(),
                timeout=self.acquire_timeout_seconds,
            )
            acquired = True
        except TimeoutError as exc:
            raise SynthesisOverloadedError(
                f"Timed out waiting {self.acquire_timeout_seconds:.1f}s for synthesis capacity.",
            ) from exc
        finally:
            async with self._lock:
                self._waiting -= 1
                if acquired:
                    self._in_flight += 1

    async def _release(self) -> None:
        async with self._lock:
            self._in_flight = max(0, self._in_flight - 1)

        self._semaphore.release()


@dataclass(frozen=True)
class AppContext:
    args: argparse.Namespace
    data_dirs: List[Path]
    voice_manager: VoiceManager
    synthesis_capacity: SynthesisCapacity
