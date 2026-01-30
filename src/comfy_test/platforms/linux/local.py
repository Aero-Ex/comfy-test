"""Local-specific behavior for Linux platform.

This module contains local development and testing utilities.
"""

import os
import subprocess
from pathlib import Path
from typing import Optional


def detect_gpu() -> bool:
    """Detect if NVIDIA GPU is available.

    Returns:
        True if nvidia-smi is available and returns success.
    """
    try:
        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=name", "--format=csv,noheader"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        return result.returncode == 0 and bool(result.stdout.strip())
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return False


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
