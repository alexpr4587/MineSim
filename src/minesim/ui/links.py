"""Project links used by the Help menu and the About dialog.

Keep every GitHub URL in this module so the menu, the issue templates and
the documentation can point at the same place.
"""

from __future__ import annotations

PROJECT_URL = "https://github.com/alexpr4587/MineSim"
PROJECT_PAGE_URL = PROJECT_URL
RELEASES_URL = f"{PROJECT_URL}/releases"
BUG_REPORT_URL = f"{PROJECT_URL}/issues/new?template=bug_report.md"
FEEDBACK_URL = f"{PROJECT_URL}/issues/new?template=feedback.md"

__all__ = [
    "BUG_REPORT_URL",
    "FEEDBACK_URL",
    "PROJECT_PAGE_URL",
    "PROJECT_URL",
    "RELEASES_URL",
]
