"""Abstract base class for platform-specific test operations."""

from abc import ABC, abstractmethod
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Callable, TYPE_CHECKING
import subprocess

if TYPE_CHECKING:
    from ..config import TestConfig


@dataclass
class TestPaths:
    """Platform-specific paths for test environment.

    Attributes:
        work_dir: Working directory for test artifacts
        comfyui_dir: ComfyUI installation directory
        python: Python executable path
        custom_nodes_dir: custom_nodes/ directory
        venv_dir: venv directory (None for portable)
    """

    work_dir: Path
    comfyui_dir: Path
    python: Path
    custom_nodes_dir: Path
    venv_dir: Optional[Path] = None

    @property
    def pip(self) -> Path:
        """Get pip executable path."""
        if self.venv_dir:
            # In venv
            bin_dir = self.venv_dir / ("Scripts" if self._is_windows() else "bin")
            return bin_dir / ("pip.exe" if self._is_windows() else "pip")
        else:
            # Portable - pip is alongside python
            return self.python.parent / ("pip.exe" if self._is_windows() else "pip")

    def _is_windows(self) -> bool:
        """Check if running on Windows."""
        import sys
        return sys.platform == "win32"


class TestPlatform(ABC):
    """
    Abstract base class for platform-specific test operations.

    Each platform (Linux, Windows, WindowsPortable) implements this
    to provide consistent test behavior across operating systems.
    """

    def __init__(self, log_callback: Optional[Callable[[str], None]] = None):
        """
        Initialize platform provider.

        Args:
            log_callback: Optional callback for logging messages
        """
        self._log = log_callback or (lambda msg: print(msg))

    @property
    @abstractmethod
    def name(self) -> str:
        """Platform name: 'linux', 'windows', 'windows_portable'."""
        pass

    @property
    @abstractmethod
    def executable_suffix(self) -> str:
        """Executable suffix: '' for Unix, '.exe' for Windows."""
        pass

    @abstractmethod
    def setup_comfyui(self, config: "TestConfig", work_dir: Path) -> TestPaths:
        """
        Set up ComfyUI for testing.

        For Linux/Windows: clone repo, create venv, install deps
        For Portable: download and extract 7z

        Args:
            config: Test configuration
            work_dir: Working directory for test artifacts

        Returns:
            TestPaths with all necessary paths
        """
        pass

    @abstractmethod
    def install_node(self, paths: TestPaths, node_dir: Path) -> None:
        """
        Install the custom node into ComfyUI.

        - Copy/symlink to custom_nodes/
        - Run install.py if present
        - Install requirements.txt

        Args:
            paths: TestPaths from setup_comfyui
            node_dir: Path to custom node source directory
        """
        pass

    @abstractmethod
    def start_server(
        self,
        paths: TestPaths,
        config: "TestConfig",
        port: int = 8188,
        extra_env: Optional[dict] = None,
    ) -> subprocess.Popen:
        """
        Start ComfyUI server.

        Args:
            paths: TestPaths from setup_comfyui
            config: Test configuration
            port: Port to listen on
            extra_env: Additional environment variables

        Returns:
            subprocess.Popen handle for the running server
        """
        pass

    def stop_server(self, process: subprocess.Popen) -> None:
        """
        Stop ComfyUI server.

        Args:
            process: Process handle from start_server
        """
        if process.poll() is None:
            process.terminate()
            try:
                process.wait(timeout=10)
            except subprocess.TimeoutExpired:
                process.kill()
                process.wait()

    @abstractmethod
    def cleanup(self, paths: TestPaths) -> None:
        """
        Clean up test environment.

        Args:
            paths: TestPaths from setup_comfyui
        """
        pass

    def _run_command(
        self,
        cmd: list[str],
        cwd: Optional[Path] = None,
        env: Optional[dict] = None,
        check: bool = True,
    ) -> subprocess.CompletedProcess:
        """
        Run a command with logging.

        Args:
            cmd: Command and arguments
            cwd: Working directory
            env: Environment variables
            check: Raise on non-zero exit

        Returns:
            CompletedProcess result
        """
        self._log(f"Running: {' '.join(str(c) for c in cmd)}")

        import os
        run_env = os.environ.copy()
        if env:
            run_env.update(env)

        result = subprocess.run(
            cmd,
            cwd=cwd,
            env=run_env,
            capture_output=True,
            text=True,
        )

        if result.stdout:
            for line in result.stdout.strip().split("\n"):
                self._log(f"  {line}")

        if result.returncode != 0 and check:
            self._log(f"Command failed with code {result.returncode}")
            if result.stderr:
                self._log(f"stderr: {result.stderr}")
            raise subprocess.CalledProcessError(
                result.returncode, cmd, result.stdout, result.stderr
            )

        return result
