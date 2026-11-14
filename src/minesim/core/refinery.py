"""The refinery: recipe jobs that turn ore into more valuable products."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

__all__ = ["RefineJob", "Refinery"]


def _get(obj: Any, name: str, default: Any = None) -> Any:
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(name, default)
    return getattr(obj, name, default)


def _recipe_entries(recipes: Any) -> dict[str, Any]:
    if recipes is None:
        return {}
    if isinstance(recipes, dict):
        return {str(key): value for key, value in recipes.items()}
    entries: dict[str, Any] = {}
    for recipe in recipes:
        recipe_id = _get(recipe, "id")
        if recipe_id is None and isinstance(recipe, dict):
            recipe_id = recipe.get("id")
        if recipe_id is not None:
            entries[str(recipe_id)] = recipe
    return entries


def _item_map(value: Any) -> dict[str, int]:
    if not isinstance(value, dict):
        return {}
    return {str(item): int(count) for item, count in value.items() if int(count) > 0}


@dataclass(slots=True)
class RefineJob:
    """One running refinery job."""

    recipe_id: str
    times: int
    started: int
    duration: int
    inputs: dict[str, int] = field(default_factory=dict)
    outputs: dict[str, int] = field(default_factory=dict)
    blocked: bool = False

    @property
    def finish_tick(self) -> int:
        """The tick at which the job finishes."""
        return int(self.started) + int(self.duration)

    def progress(self, tick: int) -> float:
        """Return the job progress in ``[0, 1]`` at ``tick``."""
        if self.duration <= 0:
            return 1.0
        elapsed = max(0, int(tick) - int(self.started))
        return min(1.0, elapsed / self.duration)

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable copy of the job."""
        return {
            "recipe_id": self.recipe_id,
            "times": int(self.times),
            "started": int(self.started),
            "duration": int(self.duration),
            "inputs": dict(self.inputs),
            "outputs": dict(self.outputs),
            "blocked": bool(self.blocked),
        }

    @classmethod
    def from_dict(cls, data: Any) -> RefineJob:
        """Rebuild a job from a :meth:`to_dict` payload."""
        if not isinstance(data, dict):
            raise ValueError("refine job data must be a mapping")
        return cls(
            recipe_id=str(data.get("recipe_id", "")),
            times=max(1, int(data.get("times", 1))),
            started=int(data.get("started", 0)),
            duration=max(0, int(data.get("duration", 0))),
            inputs=_item_map(data.get("inputs")),
            outputs=_item_map(data.get("outputs")),
            blocked=bool(data.get("blocked", False)),
        )


class Refinery:
    """A fixed number of refinery slots running recipe jobs."""

    def __init__(
        self,
        recipes: Any,
        slots: int = 1,
        progression: Any = None,
        warehouse: Any = None,
    ) -> None:
        self.recipes = _recipe_entries(recipes)
        self.slots = max(1, int(slots))
        self.progression = progression
        self.warehouse = warehouse
        self.jobs: list[RefineJob] = []
        self.tick = 0

    def set_warehouse(self, warehouse: Any) -> None:
        """Bind the warehouse that finished jobs deliver into."""
        self.warehouse = warehouse

    def get_recipe(self, recipe_id: str) -> Any:
        """Return recipe ``recipe_id`` or raise KeyError."""
        recipe_id = str(recipe_id)
        try:
            return self.recipes[recipe_id]
        except KeyError:
            raise KeyError(f"unknown recipe id '{recipe_id}'") from None

    def is_recipe_unlocked(self, recipe_id: str) -> bool:
        """Return True if the recipe is unlocked."""
        recipe = self.get_recipe(recipe_id)
        checker = getattr(self.progression, "is_recipe_unlocked", None)
        if callable(checker):
            try:
                return bool(checker(str(recipe_id)))
            except Exception:
                pass
        return _get(recipe, "unlocked_by") is None

    def _check_start(
        self, recipe_id: str, times: int, warehouse: Any
    ) -> tuple[Any, dict[str, int], dict[str, int]]:
        recipe = self.get_recipe(recipe_id)
        if not self.is_recipe_unlocked(recipe_id):
            raise ValueError("locked_recipe")
        if len(self.jobs) >= self.slots:
            raise ValueError("no_free_slot")
        if times < 1:
            raise ValueError("invalid_times")
        inputs = {
            item: int(count) * times for item, count in _item_map(_get(recipe, "inputs")).items()
        }
        outputs = {
            item: int(count) * times for item, count in _item_map(_get(recipe, "outputs")).items()
        }
        if warehouse is None:
            raise ValueError("no_warehouse")
        for item, count in inputs.items():
            if warehouse.count(item) < count:
                raise ValueError("insufficient_inputs")
        return recipe, inputs, outputs

    def start(
        self,
        recipe_id: str,
        times: int = 1,
        warehouse: Any = None,
        tick: int = 0,
    ) -> RefineJob:
        """Start ``times`` runs of ``recipe_id``.

        Validates that the recipe is unlocked, a slot is free and the
        warehouse holds every input. The inputs are removed immediately
        and a job lasting ``recipe.ticks * times`` is created.
        """
        times = int(times)
        recipe, inputs, outputs = self._check_start(recipe_id, times, warehouse)
        for item, count in inputs.items():
            warehouse.remove(item, count)
        self.warehouse = warehouse
        duration = int(_get(recipe, "ticks", 0)) * times
        job = RefineJob(
            recipe_id=str(recipe_id),
            times=times,
            started=int(tick),
            duration=duration,
            inputs=inputs,
            outputs=outputs,
        )
        self.jobs.append(job)
        self.tick = int(tick)
        return job

    def _can_deliver(self, warehouse: Any, job: RefineJob) -> bool:
        total = sum(job.outputs.values())
        free = int(getattr(warehouse, "free", total))
        return free >= total

    def advance(self, tick: int) -> list[dict[str, Any]]:
        """Finish due jobs, delivering outputs when the warehouse has room.

        A job whose outputs do not fit stays ``blocked`` in its slot and
        is retried on every later tick. Returns the finished jobs as
        dictionaries with ``recipe``, ``times`` and ``outputs``.
        """
        self.tick = int(tick)
        finished: list[dict[str, Any]] = []
        warehouse = self.warehouse
        if warehouse is None:
            return finished
        for job in list(self.jobs):
            if tick < job.finish_tick:
                continue
            if not self._can_deliver(warehouse, job):
                job.blocked = True
                continue
            for item, count in job.outputs.items():
                warehouse.add(item, count)
            self.jobs.remove(job)
            finished.append(
                {
                    "recipe": job.recipe_id,
                    "times": int(job.times),
                    "outputs": dict(job.outputs),
                }
            )
        return finished

    def status(self) -> list[dict[str, Any]]:
        """Return every job with its recipe, times and progress."""
        result: list[dict[str, Any]] = []
        for job in self.jobs:
            recipe = self.recipes.get(job.recipe_id)
            ticks_left = max(0, job.finish_tick - self.tick)
            result.append(
                {
                    "recipe": job.recipe_id,
                    "recipe_id": job.recipe_id,
                    "name": str(_get(recipe, "name", job.recipe_id)),
                    "times": int(job.times),
                    "started": int(job.started),
                    "finish_tick": job.finish_tick,
                    "duration": int(job.duration),
                    "ticks_left": ticks_left,
                    "progress": job.progress(self.tick),
                    "blocked": bool(job.blocked),
                    "inputs": dict(job.inputs),
                    "outputs": dict(job.outputs),
                }
            )
        return result

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serialisable copy of the refinery state."""
        return {
            "slots": int(self.slots),
            "tick": int(self.tick),
            "jobs": [job.to_dict() for job in self.jobs],
        }

    def from_dict(self, data: Any) -> Refinery:
        """Restore this refinery from a :meth:`to_dict` payload."""
        if not isinstance(data, dict):
            return self
        if "slots" in data:
            self.slots = max(1, int(data.get("slots", self.slots)))
        self.tick = int(data.get("tick", 0) or 0)
        jobs: list[RefineJob] = []
        for entry in data.get("jobs", []) or []:
            try:
                jobs.append(RefineJob.from_dict(entry))
            except (TypeError, ValueError):
                continue
        self.jobs = jobs
        return self

    @classmethod
    def load(
        cls,
        data: Any,
        recipes: Any,
        slots: int = 1,
        progression: Any = None,
        warehouse: Any = None,
    ) -> Refinery:
        """Build a refinery from a :meth:`to_dict` payload."""
        refinery = cls(recipes, slots, progression, warehouse)
        refinery.from_dict(data)
        return refinery
