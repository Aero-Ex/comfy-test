"""Platform abstraction for cross-platform testing."""

import sys
from typing import Optional, Callable

from .base import TestPlatform, TestPaths


def get_platform(
    name: Optional[str] = None,
    log_callback: Optional[Callable[[str], None]] = None,
) -> TestPlatform:
    """
    Get the appropriate platform provider.

    Args:
        name: Platform name ('linux', 'macos', 'windows', 'windows_portable', 'windows-portable')
              If None, auto-detects current platform.
        log_callback: Optional callback for logging messages

    Returns:
        TestPlatform instance for the specified platform

    Raises:
        ValueError: If platform is not supported

    Example:
        >>> platform = get_platform("linux")
        >>> paths = platform.setup_comfyui(config, work_dir)
    """
    if name is None:
        name = _detect_platform()

    # Normalize name
    name = name.lower().replace("-", "_")

    if name == "linux":
        from .linux import LinuxTestPlatform
        return LinuxTestPlatform(log_callback)
    elif name == "macos":
        from .macos import MacOSTestPlatform
        return MacOSTestPlatform(log_callback)
    elif name == "windows":
        from .windows import WindowsTestPlatform
        return WindowsTestPlatform(log_callback)
    elif name == "windows_portable":
        if sys.platform != "win32":
            raise ValueError(
                "windows_portable tests can only run on Windows. "
                "On Linux/macOS, use the 'linux' or 'macos' platform instead."
            )
        from .windows_portable import WindowsPortableTestPlatform
        return WindowsPortableTestPlatform(log_callback)
    else:
        raise ValueError(
            f"Unsupported platform: {name}. "
            f"Supported: linux, macos, windows, windows_portable"
        )


def _detect_platform() -> str:
    """Detect current platform."""
    if sys.platform == "linux":
        return "linux"
    elif sys.platform == "darwin":
        return "macos"
    elif sys.platform == "win32":
        return "windows"
    else:
        raise ValueError(f"Unknown platform: {sys.platform}")


__all__ = [
    "TestPlatform",
    "TestPaths",
    "get_platform",
]
