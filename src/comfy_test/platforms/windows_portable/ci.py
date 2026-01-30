"""CI-specific behavior for Windows Portable platform."""

import os
from pathlib import Path
from typing import Dict


def is_ci_environment() -> bool:
    """Check if running in a CI environment."""
    return os.environ.get("CI") == "true" or os.environ.get("GITHUB_ACTIONS") == "true"


def get_ci_env_vars() -> Dict[str, str]:
    """Get environment variables specific to CI runs."""
    env = {}
    if os.environ.get("GITHUB_ACTIONS"):
        env["CI"] = "true"
    return env
