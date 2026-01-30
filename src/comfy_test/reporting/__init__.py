"""Report generation and output utilities."""

from .merge import (
    merge_results,
    merge_with_gh_pages,
    fetch_existing_results,
    clone_gh_pages,
    merge_assets,
)
from .screenshot_cache import ScreenshotCache

# Note: html_report and screenshot modules are large and imported on-demand
# to avoid slow startup times

__all__ = [
    "merge_results",
    "merge_with_gh_pages",
    "fetch_existing_results",
    "clone_gh_pages",
    "merge_assets",
    "ScreenshotCache",
]
