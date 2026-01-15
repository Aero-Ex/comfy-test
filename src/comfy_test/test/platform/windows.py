"""Windows platform implementation for ComfyUI testing."""

import os
import shutil
import subprocess
from pathlib import Path
from typing import Optional, Callable, TYPE_CHECKING

from .base import TestPlatform, TestPaths

if TYPE_CHECKING:
    from ..config import TestConfig


COMFYUI_REPO = "https://github.com/comfyanonymous/ComfyUI.git"
PYTORCH_CPU_INDEX = "https://download.pytorch.org/whl/cpu"


class WindowsTestPlatform(TestPlatform):
    """Windows platform implementation for ComfyUI testing (venv-based)."""

    @property
    def name(self) -> str:
        return "windows"

    @property
    def executable_suffix(self) -> str:
        return ".exe"

    def setup_comfyui(self, config: "TestConfig", work_dir: Path) -> TestPaths:
        """
        Set up ComfyUI for testing on Windows.

        1. Clone ComfyUI from GitHub
        2. Create venv with uv
        3. Install requirements
        4. Install PyTorch (CPU)
        """
        work_dir = Path(work_dir)
        work_dir.mkdir(parents=True, exist_ok=True)

        comfyui_dir = work_dir / "ComfyUI"
        venv_dir = work_dir / "venv"

        # Clone ComfyUI
        self._log(f"Cloning ComfyUI ({config.comfyui_version})...")
        if comfyui_dir.exists():
            shutil.rmtree(comfyui_dir)

        clone_args = ["git", "clone", "--depth", "1"]
        if config.comfyui_version != "latest":
            clone_args.extend(["--branch", config.comfyui_version])
        clone_args.extend([COMFYUI_REPO, str(comfyui_dir)])

        self._run_command(clone_args, cwd=work_dir)

        # Create venv with uv
        self._log(f"Creating venv (Python {config.python_version})...")
        if venv_dir.exists():
            shutil.rmtree(venv_dir)

        self._run_command(
            ["uv", "venv", str(venv_dir), "--python", config.python_version],
            cwd=work_dir,
        )

        python = venv_dir / "Scripts" / "python.exe"
        pip = venv_dir / "Scripts" / "pip.exe"

        # Install PyTorch (CPU)
        self._log("Installing PyTorch (CPU)...")
        self._run_command(
            ["uv", "pip", "install", "--python", str(python),
             "torch", "torchvision", "torchaudio",
             "--index-url", PYTORCH_CPU_INDEX],
            cwd=work_dir,
        )

        # Install ComfyUI requirements
        self._log("Installing ComfyUI requirements...")
        requirements_file = comfyui_dir / "requirements.txt"
        if requirements_file.exists():
            self._run_command(
                ["uv", "pip", "install", "--python", str(python),
                 "-r", str(requirements_file)],
                cwd=work_dir,
            )

        custom_nodes_dir = comfyui_dir / "custom_nodes"
        custom_nodes_dir.mkdir(exist_ok=True)

        return TestPaths(
            work_dir=work_dir,
            comfyui_dir=comfyui_dir,
            python=python,
            custom_nodes_dir=custom_nodes_dir,
            venv_dir=venv_dir,
        )

    def install_node(self, paths: TestPaths, node_dir: Path) -> None:
        """
        Install custom node into ComfyUI.

        On Windows, we copy instead of symlink to avoid permission issues.

        1. Copy to custom_nodes/
        2. Run install.py if present
        3. Install requirements.txt if present
        """
        node_dir = Path(node_dir).resolve()
        node_name = node_dir.name

        target_dir = paths.custom_nodes_dir / node_name

        # Copy node directory
        self._log(f"Copying {node_name} to custom_nodes/...")
        if target_dir.exists():
            shutil.rmtree(target_dir)

        shutil.copytree(node_dir, target_dir)

        # Install requirements.txt first (install.py may depend on these)
        requirements_file = target_dir / "requirements.txt"
        if requirements_file.exists():
            self._log("Installing node requirements...")
            self._run_command(
                ["uv", "pip", "install", "--python", str(paths.python),
                 "-r", str(requirements_file)],
                cwd=target_dir,
            )

        # Run install.py if present
        install_py = target_dir / "install.py"
        if install_py.exists():
            self._log("Running install.py...")
            # Set CUDA version for CPU-only CI (comfy-env will use this if no GPU detected)
            install_env = {"COMFY_ENV_CUDA_VERSION": "12.8"}
            self._run_command(
                [str(paths.python), str(install_py)],
                cwd=target_dir,
                env=install_env,
            )

    def start_server(
        self,
        paths: TestPaths,
        config: "TestConfig",
        port: int = 8188,
        extra_env: Optional[dict] = None,
    ) -> subprocess.Popen:
        """Start ComfyUI server on Windows."""
        self._log(f"Starting ComfyUI server on port {port}...")

        cmd = [
            str(paths.python),
            str(paths.comfyui_dir / "main.py"),
            "--listen", "127.0.0.1",
            "--port", str(port),
        ]

        if config.cpu_only:
            cmd.append("--cpu")

        # Set environment
        env = os.environ.copy()
        if paths.venv_dir:
            env["VIRTUAL_ENV"] = str(paths.venv_dir)
            env["PATH"] = f"{paths.venv_dir}\\Scripts;{env.get('PATH', '')}"
        if extra_env:
            env.update(extra_env)

        process = subprocess.Popen(
            cmd,
            cwd=paths.comfyui_dir,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )

        return process

    def cleanup(self, paths: TestPaths) -> None:
        """Clean up test environment on Windows."""
        self._log(f"Cleaning up {paths.work_dir}...")

        if paths.work_dir.exists():
            # Windows sometimes has file locking issues
            try:
                shutil.rmtree(paths.work_dir)
            except PermissionError:
                self._log("Warning: Could not fully clean up (files may be locked)")
