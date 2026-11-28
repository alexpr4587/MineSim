"""Load and validate the EventBus to sound mapping (audio_events.json)."""

from __future__ import annotations

import dataclasses
import importlib
from pathlib import Path
from typing import Any

from pydantic import ValidationError

from minesim.audio.content import read_content_json
from minesim.core.schemas import AudioEventRule, ContentError

__all__ = [
    "DERIVED_FIELDS",
    "EVENT_TYPES",
    "condition_matches",
    "load_audio_events",
    "rule_matches",
]

_OPERATORS = {"lt", "lte", "gt", "gte", "eq", "ne", "in", "not_in"}
DERIVED_FIELDS: dict[str, frozenset[str]] = {
    "LayerChanged": frozenset({"direction"}),
}


def _event_classes() -> dict[str, type[Any]]:
    module = importlib.import_module("minesim.core.events")
    classes: dict[str, type[Any]] = {}
    for name in dir(module):
        candidate = getattr(module, name)
        if dataclasses.is_dataclass(candidate) and isinstance(candidate, type):
            classes[name] = candidate
    return classes


EVENT_TYPES: dict[str, type[Any]] = _event_classes()


def _field_names(event_name: str) -> frozenset[str]:
    event_type = EVENT_TYPES[event_name]
    return frozenset(field.name for field in dataclasses.fields(event_type))


def _value(event: Any, name: str) -> Any:
    if isinstance(event, dict):
        return event.get(name)
    return getattr(event, name, None)


def _derived(event: Any, name: str) -> Any:
    if name == "direction":
        from_layer = int(_value(event, "from_layer") or 0)
        to_layer = int(_value(event, "to_layer") or 0)
        return "down" if to_layer > from_layer else "up"
    return None


def condition_matches(event: Any, conditions: dict[str, Any]) -> bool:
    """Return True when ``event`` satisfies every condition."""
    for field, expected in conditions.items():
        actual = (
            _derived(event, field)
            if field in DERIVED_FIELDS.get(type(event).__name__, frozenset())
            else _value(event, field)
        )
        if isinstance(expected, dict):
            for operator, target in expected.items():
                if not _compare(actual, str(operator), target):
                    return False
        elif actual != expected:
            return False
    return True


def _compare(actual: Any, operator: str, target: Any) -> bool:
    try:
        if operator == "lt":
            return actual < target
        if operator == "lte":
            return actual <= target
        if operator == "gt":
            return actual > target
        if operator == "gte":
            return actual >= target
        if operator == "eq":
            return actual == target
        if operator == "ne":
            return actual != target
        if operator == "in":
            return actual in target
        if operator == "not_in":
            return actual not in target
    except (TypeError, ValueError):
        return False
    return False


def rule_matches(rule: AudioEventRule, event: Any) -> bool:
    """Return True when ``rule`` applies to ``event``."""
    return condition_matches(event, dict(rule.when))


def _validate_rule(rule: AudioEventRule, index: int) -> None:
    event_name = rule.event
    if event_name not in EVENT_TYPES:
        raise ContentError(f"audio_events.json: $.{index}.event: unknown event '{event_name}'")
    fields = _field_names(event_name) | DERIVED_FIELDS.get(event_name, frozenset())
    for field, expected in rule.when.items():
        if field not in fields:
            raise ContentError(
                f"audio_events.json: $.{index}.when.{field}: "
                f"event '{event_name}' has no field '{field}'"
            )
        if isinstance(expected, dict):
            for operator in expected:
                if operator not in _OPERATORS:
                    raise ContentError(
                        f"audio_events.json: $.{index}.when.{field}.{operator}: "
                        f"unknown operator '{operator}'"
                    )
    if rule.pitch not in {"", "combo"}:
        raise ContentError(f"audio_events.json: $.{index}.pitch: unknown pitch mode '{rule.pitch}'")


def load_audio_events(
    content_dir: str | Path | None = None,
    sounds: dict[str, Any] | None = None,
) -> list[AudioEventRule]:
    """Load, validate and return the audio event rules.

    Every referenced event and sound must exist; errors name the file and
    the JSON path.
    """
    if sounds is None:
        from minesim.audio.recipes import load_sfx_recipes

        sounds = load_sfx_recipes(content_dir)
    data: Any = read_content_json("audio_events.json", content_dir)
    if isinstance(data, dict):
        data = data.get("events", data)
    if not isinstance(data, list):
        raise ContentError("audio_events.json: $: expected a list of event rules")
    rules: list[AudioEventRule] = []
    for index, item in enumerate(data):
        try:
            rule = AudioEventRule.model_validate(item)
        except ValidationError as exc:
            errors = exc.errors(include_url=False)
            first = errors[0] if errors else {}
            location = ".".join(str(part) for part in first.get("loc", ()))
            path = f"$.{index}" + (f".{location}" if location else "")
            message = str(first.get("msg", "invalid value"))
            raise ContentError(f"audio_events.json: {path}: {message}") from None
        _validate_rule(rule, index)
        if rule.sound not in sounds:
            raise ContentError(f"audio_events.json: $.{index}.sound: unknown sound '{rule.sound}'")
        rules.append(rule)
    return rules
