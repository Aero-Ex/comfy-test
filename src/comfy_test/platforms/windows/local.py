"""Local-specific behavior for Windows platform.

This module contains local development and testing utilities.
"""

import os
from pathlib import Path
from typing import Optional


def get_local_wheels_path() -> Optional[Path]:
    """Get path to local wheels directory if set.

    Returns:
        Path to local wheels or None if not set.
    """
    local_wheels = os.environ.get("COMFY_LOCAL_WHEELS")
    if local_wheels:
        path = Path(local_wheels)
        if path.exists():
            return path
    return None


def is_gpu_mode_enabled() -> bool:
    """Check if GPU mode is enabled via environment variable."""
    return bool(os.environ.get("COMFY_TEST_GPU"))


# Local dev packages to build wheels for
LOCAL_DEV_PACKAGES = [
    ("comfy-env", Path.home() / "Desktop" / "utils" / "comfy-env"),
    ("comfy-test", Path.home() / "Desktop" / "utils" / "comfy-test"),
]


def get_local_dev_packages():
    """Get list of local dev packages that exist.

    Returns:
        List of (name, path) tuples for existing packages.
    """
    return [(name, path) for name, path in LOCAL_DEV_PACKAGES if path.exists()]
