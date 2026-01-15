"""ComfyUI server management."""

import subprocess
import time
from pathlib import Path
from typing import Optional, Callable, List, TYPE_CHECKING

from .api import ComfyUIAPI
from ..errors import ServerError, TimeoutError

if TYPE_CHECKING:
    from ..test.platform.base import TestPaths, TestPlatform
    from ..test.config import TestConfig


class ComfyUIServer:
    """Manages ComfyUI server lifecycle.

    Handles starting, waiting for readiness, and stopping the ComfyUI server.

    Args:
        platform: Platform provider for server operations
        paths: Test paths from platform setup
        config: Test configuration
        port: Port to listen on
        cuda_mock_packages: List of CUDA packages to mock for import testing
        log_callback: Optional callback for logging

    Example:
        >>> with ComfyUIServer(platform, paths, config) as server:
        ...     api = server.get_api()
        ...     nodes = api.get_object_info()
    """

    def __init__(
        self,
        platform: "TestPlatform",
        paths: "TestPaths",
        config: "TestConfig",
        port: int = 8188,
        cuda_mock_packages: Optional[List[str]] = None,
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        self.platform = platform
        self.paths = paths
        self.config = config
        self.port = port
        self.cuda_mock_packages = cuda_mock_packages or []
        self._log = log_callback or (lambda msg: print(msg))
        self._process: Optional[subprocess.Popen] = None
        self._api: Optional[ComfyUIAPI] = None

    @property
    def base_url(self) -> str:
        """Get server base URL."""
        return f"http://127.0.0.1:{self.port}"

    def start(self, wait_timeout: int = 60) -> None:
        """Start the ComfyUI server and wait for it to be ready.

        Args:
            wait_timeout: Maximum seconds to wait for server to be ready

        Raises:
            ServerError: If server fails to start
            TimeoutError: If server doesn't become ready in time
        """
        if self._process is not None:
            raise ServerError("Server already started")

        self._log(f"Starting ComfyUI server on port {self.port}...")

        # Prepare extra env vars for CUDA mock injection
        extra_env = {}
        if self.cuda_mock_packages:
            extra_env["COMFY_TEST_MOCK_PACKAGES"] = ",".join(self.cuda_mock_packages)
            extra_env["COMFY_TEST_STRICT_IMPORTS"] = "1"
            self._log(f"CUDA mock packages: {', '.join(self.cuda_mock_packages)}")

        self._process = self.platform.start_server(
            self.paths,
            self.config,
            self.port,
            extra_env=extra_env,
        )

        # Wait for server to be ready
        self._wait_for_ready(wait_timeout)

    def _wait_for_ready(self, timeout: int) -> None:
        """Wait for server to become responsive.

        Args:
            timeout: Maximum seconds to wait

        Raises:
            TimeoutError: If server doesn't respond in time
            ServerError: If server process dies
        """
        self._log(f"Waiting for server to be ready (timeout: {timeout}s)...")
        api = ComfyUIAPI(self.base_url, timeout=5)

        start_time = time.time()
        last_error = None

        while time.time() - start_time < timeout:
            # Check if process died
            if self._process and self._process.poll() is not None:
                stdout, stderr = self._process.communicate()
                raise ServerError(
                    "ComfyUI server exited unexpectedly",
                    f"Exit code: {self._process.returncode}\n"
                    f"stdout: {stdout}\n"
                    f"stderr: {stderr}"
                )

            try:
                if api.health_check():
                    self._log("Server is ready!")
                    self._api = api
                    return
            except Exception as e:
                last_error = e

            time.sleep(1)

        # Timeout reached
        api.close()
        raise TimeoutError(
            f"Server did not become ready within {timeout} seconds",
            timeout_seconds=timeout,
        )

    def stop(self) -> None:
        """Stop the ComfyUI server."""
        if self._process is None:
            return

        self._log("Stopping ComfyUI server...")

        if self._api:
            self._api.close()
            self._api = None

        self.platform.stop_server(self._process)
        self._process = None

    def get_api(self) -> ComfyUIAPI:
        """Get API client for the running server.

        Returns:
            ComfyUIAPI instance

        Raises:
            ServerError: If server is not running
        """
        if self._api is None:
            raise ServerError("Server is not running")
        return self._api

    def __enter__(self) -> "ComfyUIServer":
        self.start()
        return self

    def __exit__(self, *args) -> None:
        self.stop()
