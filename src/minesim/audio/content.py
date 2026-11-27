"""Read the audio content JSON files from the package or a test directory."""

from __future__ import annotations

import json
from importlib.resources import files
from pathlib import Path
from typing import Any

from minesim.core.schemas import ContentError

__all__ = ["read_content_json", "read_content_text"]


def read_content_text(filename: str, content_dir: str | Path | None = None) -> str:
    """Return the text of ``filename`` from ``content_dir`` or the package."""
    if content_dir is not None:
        path = Path(content_dir) / filename
        try:
            return path.read_text(encoding="utf-8")
        except FileNotFoundError:
            raise ContentError(f"{filename}: file not found: {path}") from None
        except OSError as exc:
            raise ContentError(f"{filename}: could not read file: {exc}") from None
    try:
        return files("minesim").joinpath("content").joinpath(filename).read_text(encoding="utf-8")
    except FileNotFoundError:
        raise ContentError(f"{filename}: file not found in the packaged content") from None
    except OSError as exc:
        raise ContentError(f"{filename}: could not read file: {exc}") from None


def read_content_json(filename: str, content_dir: str | Path | None = None) -> Any:
    """Read and parse a content JSON file."""
    text = read_content_text(filename, content_dir)
    try:
        return json.loads(text)
    except json.JSONDecodeError as exc:
        raise ContentError(f"{filename}: $: invalid JSON: {exc}") from None
