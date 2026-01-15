"""Configuration dataclasses for installation tests."""

from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


@dataclass
class WorkflowConfig:
    """Configuration for test workflow execution.

    Args:
        file: Path to workflow JSON file (relative to node directory)
        timeout: Timeout in seconds for workflow execution
    """

    file: Optional[Path] = None
    timeout: int = 120

    def __post_init__(self):
        """Validate and normalize configuration."""
        if self.file is not None:
            self.file = Path(self.file)
        if self.timeout <= 0:
            raise ValueError(f"Timeout must be positive, got {self.timeout}")


@dataclass
class PlatformTestConfig:
    """Platform-specific test configuration.

    Args:
        enabled: Whether to run tests on this platform
        skip_workflow: Skip workflow execution (only verify node registration)
        comfyui_portable_version: Version of portable ComfyUI to use (Windows portable only)
    """

    enabled: bool = True
    skip_workflow: bool = False
    comfyui_portable_version: Optional[str] = None


@dataclass
class TestConfig:
    """
    Configuration for installation tests.

    Parsed from comfy-test.toml in the custom node directory.

    Args:
        name: Test suite name (usually node package name)
        comfyui_version: ComfyUI version ("latest", tag, or commit hash)
        python_version: Python version for venv (e.g., "3.10")
        cpu_only: Use --cpu flag (no GPU required)
        timeout: Global timeout in seconds for setup operations
        expected_nodes: Node names that must exist after install
        workflow: Optional workflow to execute for end-to-end testing
        linux: Linux-specific test configuration
        windows: Windows-specific test configuration
        windows_portable: Windows Portable-specific test configuration

    Example:
        config = TestConfig(
            name="ComfyUI-MyNode",
            expected_nodes=["MyNode1", "MyNode2"],
            workflow=WorkflowConfig(file=Path("tests/workflows/smoke.json")),
        )
    """

    name: str
    comfyui_version: str = "latest"
    python_version: str = "3.10"
    cpu_only: bool = True
    timeout: int = 300
    expected_nodes: List[str] = field(default_factory=list)
    workflow: WorkflowConfig = field(default_factory=WorkflowConfig)
    linux: PlatformTestConfig = field(default_factory=PlatformTestConfig)
    windows: PlatformTestConfig = field(default_factory=PlatformTestConfig)
    windows_portable: PlatformTestConfig = field(default_factory=PlatformTestConfig)

    def __post_init__(self):
        """Validate configuration."""
        if not self.name:
            raise ValueError("Test name is required")

        # Validate Python version format
        if not self.python_version.replace(".", "").isdigit():
            raise ValueError(f"Invalid Python version: {self.python_version}")

        # Validate timeout
        if self.timeout <= 0:
            raise ValueError(f"Timeout must be positive, got {self.timeout}")

        # Ensure workflow is WorkflowConfig
        if isinstance(self.workflow, dict):
            self.workflow = WorkflowConfig(**self.workflow)

        # Ensure platform configs are PlatformTestConfig
        if isinstance(self.linux, dict):
            self.linux = PlatformTestConfig(**self.linux)
        if isinstance(self.windows, dict):
            self.windows = PlatformTestConfig(**self.windows)
        if isinstance(self.windows_portable, dict):
            self.windows_portable = PlatformTestConfig(**self.windows_portable)

    @property
    def python_short(self) -> str:
        """Get Python version without dots (e.g., '310' for '3.10')."""
        return self.python_version.replace(".", "")

    def get_platform_config(self, platform: str) -> PlatformTestConfig:
        """Get configuration for a specific platform.

        Args:
            platform: Platform name ('linux', 'windows', 'windows_portable')

        Returns:
            PlatformTestConfig for the specified platform

        Raises:
            ValueError: If platform is not recognized
        """
        platform_map = {
            "linux": self.linux,
            "windows": self.windows,
            "windows_portable": self.windows_portable,
            "windows-portable": self.windows_portable,  # Allow hyphen variant
        }
        if platform not in platform_map:
            raise ValueError(f"Unknown platform: {platform}")
        return platform_map[platform]
