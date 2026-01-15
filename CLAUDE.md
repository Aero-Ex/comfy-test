# CLAUDE.md

This file provides guidance to Claude Code when working with this repository.

## Project Overview

**comfy-test** is a Python library for testing ComfyUI custom node installations across multiple platforms (Linux, Windows, Windows Portable).

Custom nodes just add a config file + workflow file - no pytest code needed.

## How Custom Nodes Use This

```
MyCustomNode/
├── comfy-test.toml                    # Config: what nodes to verify, what workflow to run
├── tests/workflows/smoke_test.json    # A minimal ComfyUI workflow to test
└── .github/workflows/test-install.yml # One-liner calling reusable workflow
```

That's it! The reusable workflow handles:
- Setting up ComfyUI
- Installing the node
- Verifying nodes load
- Running the test workflow

## Key Components

| File | Purpose |
|------|---------|
| `src/comfy_test/test/config.py` | TestConfig dataclass |
| `src/comfy_test/test/config_file.py` | TOML parsing |
| `src/comfy_test/test/platform/` | Platform providers (Linux/Windows/Portable) |
| `src/comfy_test/test/manager.py` | Test orchestration |
| `src/comfy_test/comfyui/` | ComfyUI server/API interaction |
| `src/comfy_test/cli.py` | CLI entry point |
| `.github/workflows/test-matrix.yml` | Reusable workflow for consumers |

## Development

```bash
pip install -e .
comfy-test info
comfy-test run --platform linux --dry-run
```

## Config Format

```toml
[test]
name = "MyNode"

[test.verification]
expected_nodes = ["Node1", "Node2"]

[test.workflow]
file = "tests/workflows/smoke.json"
timeout = 120
```
