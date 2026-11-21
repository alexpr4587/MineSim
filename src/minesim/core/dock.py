"""The shared surface dock and its FIFO service queue."""

from __future__ import annotations

from dataclasses import dataclass

__all__ = ["Dock", "DockJob"]


@dataclass(slots=True)
class DockJob:
    """One miner's request to move ``units`` through the surface dock."""

    miner_id: int = 0
    units: int = 0
    arrival_tick: int = 0
    service_ticks: int = 1
    start_tick: int | None = None


class Dock:
    """A single service point shared by every miner on the surface base.

    Jobs are served first-in, first-out. Ties on ``arrival_tick`` are
    broken by ``miner_id`` so the order is deterministic.
    """

    def __init__(self, rate: int = 4) -> None:
        self.rate = max(1, int(rate))
        self._busy: DockJob | None = None
        self._queue: list[DockJob] = []

    @property
    def free(self) -> bool:
        """Return True when no miner is currently being served."""
        return self._busy is None

    @property
    def queue_length(self) -> int:
        """Return how many jobs are waiting behind the busy one."""
        return len(self._queue)

    @property
    def busy(self) -> DockJob | None:
        """The job currently being served, if any."""
        return self._busy

    @property
    def busy_job(self) -> DockJob | None:
        """The job currently being served, if any."""
        return self._busy

    @property
    def queue(self) -> list[DockJob]:
        """The waiting jobs in service order."""
        self._sort_queue()
        return list(self._queue)

    @property
    def waiting_jobs(self) -> tuple[DockJob, ...]:
        """The queued jobs in service order."""
        return tuple(self.queue)

    def service_ticks(self, units: int) -> int:
        """Return the ticks needed to move ``units`` at the current rate."""
        rate = max(1, int(self.rate))
        return max(1, (max(0, int(units)) + rate - 1) // rate)

    def enqueue(self, job: DockJob, tick: int) -> bool:
        """Add ``job`` and return True when it starts immediately."""
        job.arrival_tick = int(tick)
        if self._busy is None:
            job.start_tick = int(tick)
            self._busy = job
            return True
        self._queue.append(job)
        self._sort_queue()
        return False

    def cancel(self, job: DockJob, tick: int) -> bool:
        """Remove ``job`` from the dock, promoting the next waiting job."""
        if self._busy is job:
            self._busy = None
            self._start_next(int(tick))
            return True
        for index, waiting in enumerate(self._queue):
            if waiting is job:
                self._queue.pop(index)
                return True
        return False

    def advance(self, tick: int) -> list[DockJob]:
        """Complete jobs that finished by ``tick`` and start the next one."""
        tick = int(tick)
        completed: list[DockJob] = []
        if self._busy is None:
            self._start_next(tick)
        while self._busy is not None:
            job = self._busy
            start = int(job.start_tick if job.start_tick is not None else tick)
            if tick - start < max(1, int(job.service_ticks)):
                break
            completed.append(job)
            self._busy = None
            if not self._start_next(tick):
                break
        return completed

    def eta_ticks(self, tick: int) -> int:
        """Return the estimated ticks until the dock is free again."""
        tick = int(tick)
        total = 0
        if self._busy is not None:
            start = int(self._busy.start_tick if self._busy.start_tick is not None else tick)
            total += max(0, start + max(1, int(self._busy.service_ticks)) - tick)
        for job in self._queue:
            total += max(1, int(job.service_ticks))
        return total

    def status(self, tick: int) -> dict[str, int | bool]:
        """Return the public dock status payload."""
        return {
            "free": self.free,
            "queue_length": self.queue_length,
            "eta_ticks": self.eta_ticks(tick),
            "rate": max(1, int(self.rate)),
        }

    def _sort_queue(self) -> None:
        self._queue.sort(key=lambda job: (int(job.arrival_tick), int(job.miner_id)))

    def _start_next(self, tick: int) -> bool:
        if self._busy is not None or not self._queue:
            return False
        self._sort_queue()
        job = self._queue.pop(0)
        job.start_tick = int(tick)
        self._busy = job
        return True
