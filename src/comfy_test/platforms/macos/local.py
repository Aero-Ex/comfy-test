"""Local-specific behavior for macOS platform."""

import os
import subprocess
from pathlib import Path
from typing import Optional


def is_gpu_mode_enabled() -> bool:
    """Check if GPU mode is enabled via environment variable."""
    return bool(os.environ.get("COMFY_TEST_GPU"))


def detect_apple_silicon() -> bool:
    """Detect if running on Apple Silicon (M1/M2/M3).

    Returns:
        True if running on Apple Silicon, False otherwise.
    """
    import platform
    return platform.machine() == "arm64"


def detect_mps_available() -> bool:
    """Detect if MPS (Metal Performance Shaders) is available.

    Returns:
        True if MPS is available for GPU acceleration.
    """
    try:
        import torch
        return torch.backends.mps.is_available()
    except (ImportError, AttributeError):
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
