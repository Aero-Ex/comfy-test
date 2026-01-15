"""
comfy-test: Installation testing infrastructure for ComfyUI custom nodes.

This package provides:
- Multi-platform installation testing (Linux, Windows, Windows Portable)
- Workflow execution verification
- GitHub Actions integration

## Quick Start

    from comfy_test import run_tests, verify_nodes

    # Run all tests from config
    results = run_tests()

    # Or verify nodes only
    results = verify_nodes()

## CLI

    comfy-test run              # Run installation tests
    comfy-test verify           # Verify node registration
    comfy-test info             # Show configuration
    comfy-test init-ci          # Generate GitHub Actions workflow

## Configuration

Create comfy-test.toml in your custom node directory:

    [test]
    name = "MyNode"
    expected_nodes = ["MyNode1", "MyNode2"]

    [test.workflow]
    file = "tests/workflows/smoke_test.json"

## GitHub Actions

Add this workflow to your repository:

    # .github/workflows/test-install.yml
    name: Test Installation
    on: [push, pull_request]

    jobs:
      test:
        uses: PozzettiAndrea/comfy-test/.github/workflows/test-matrix.yml@main
        with:
          config-file: "comfy-test.toml"
"""

__version__ = "0.0.1"

from .test.config import TestConfig, WorkflowConfig, PlatformTestConfig
from .test.config_file import load_config, discover_config, CONFIG_FILE_NAMES
from .test.manager import TestManager, TestResult
from .errors import (
    TestError,
    ConfigError,
    SetupError,
    ServerError,
    WorkflowError,
    VerificationError,
    TimeoutError,
    DownloadError,
)

# Convenience functions
from .runner import run_tests, verify_nodes

__all__ = [
    # Config
    "TestConfig",
    "WorkflowConfig",
    "PlatformTestConfig",
    "load_config",
    "discover_config",
    "CONFIG_FILE_NAMES",
    # Manager
    "TestManager",
    "TestResult",
    # Errors
    "TestError",
    "ConfigError",
    "SetupError",
    "ServerError",
    "WorkflowError",
    "VerificationError",
    "TimeoutError",
    "DownloadError",
    # Convenience
    "run_tests",
    "verify_nodes",
]
