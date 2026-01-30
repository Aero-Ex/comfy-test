"""Local-specific behavior for Windows Portable platform."""

import os
from pathlib import Path
from typing import Optional


def is_gpu_mode_enabled() -> bool:
    """Check if GPU mode is enabled via environment variable."""
    return bool(os.environ.get("COMFY_TEST_GPU"))


def get_portable_cache_dir() -> Path:
    """Get the cache directory for portable downloads."""
    cache_dir = Path.home() / ".comfy-test" / "cache" / "portable"
    cache_dir.mkdir(parents=True, exist_ok=True)
    return cache_dir
