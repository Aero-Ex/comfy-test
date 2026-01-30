"""CI-specific behavior for Linux platform.

This module contains GitHub Actions and CI-specific configuration and utilities.
"""

import os
from pathlib import Path
from typing import Dict, Any


def get_ci_env_vars() -> Dict[str, str]:
    """Get environment variables specific to CI runs.

    Returns:
        Dict of environment variables to set in CI.
    """
    env = {}

    # GitHub Actions specific
    if os.environ.get("GITHUB_ACTIONS"):
        env["CI"] = "true"

    return env


def get_ci_cache_paths(work_dir: Path) -> Dict[str, Path]:
    """Get paths that should be cached in CI.

    Args:
        work_dir: Working directory for test artifacts

    Returns:
        Dict mapping cache key to path.
    """
    return {
        "pip": Path.home() / ".cache" / "pip",
        "uv": Path.home() / ".cache" / "uv",
    }


def is_ci_environment() -> bool:
    """Check if running in a CI environment."""
    return os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"
