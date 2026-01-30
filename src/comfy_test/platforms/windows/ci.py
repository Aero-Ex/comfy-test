"""CI-specific behavior for Windows platform.

This module contains GitHub Actions and CI-specific configuration and utilities.
"""

import os
from pathlib import Path
from typing import Dict


def get_ci_python() -> Path:
    """Get the CI venv Python path for GitHub Actions.

    Returns:
        Path to Python executable in the CI venv.
    """
    return Path.home() / "venv" / "venv" / "Scripts" / "python.exe"


def is_ci_environment() -> bool:
    """Check if running in a CI environment."""
    return os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"


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
