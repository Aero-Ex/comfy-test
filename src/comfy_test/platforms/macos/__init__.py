"""macOS platform implementation."""

from .platform import MacOSPlatform
from .ci import is_ci_environment, get_ci_env_vars
from .local import (
    is_gpu_mode_enabled,
    detect_apple_silicon,
    detect_mps_available,
    get_local_wheels_path,
)

__all__ = [
    "MacOSPlatform",
    "is_ci_environment",
    "get_ci_env_vars",
    "is_gpu_mode_enabled",
    "detect_apple_silicon",
    "detect_mps_available",
    "get_local_wheels_path",
]
