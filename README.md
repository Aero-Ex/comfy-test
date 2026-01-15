# comfy-test

Installation testing infrastructure for ComfyUI custom nodes.

Test your nodes install and work correctly across **Linux**, **Windows**, and **Windows Portable** - with just config files, no pytest code needed.

## Quick Start

Add these files to your custom node repository:

### 1. `comfy-test.toml`

```toml
[test]
name = "ComfyUI-MyNode"

[test.verification]
expected_nodes = ["MyNode1", "MyNode2"]

[test.workflow]
file = "tests/workflows/smoke_test.json"
timeout = 120
```

### 2. `.github/workflows/test-install.yml`

```yaml
name: Test Installation
on: [push, pull_request]

jobs:
  test:
    uses: PozzettiAndrea/comfy-test/.github/workflows/test-matrix.yml@main
```

### 3. `tests/workflows/smoke_test.json`

A minimal ComfyUI workflow that uses your nodes. Export from ComfyUI.

**Done!** Push to GitHub and your tests will run automatically on all platforms.

## What It Tests

1. **Setup** - Clones ComfyUI, creates environment, installs dependencies
2. **Install** - Copies your node, runs `install.py`, installs `requirements.txt`
3. **Verify** - Starts ComfyUI, checks your nodes appear in `/object_info`
4. **Execute** - Runs your test workflow, verifies it completes without errors

## Configuration Reference

```toml
[test]
name = "ComfyUI-MyNode"           # Test suite name
comfyui_version = "latest"        # ComfyUI version (tag, commit, or "latest")
python_version = "3.10"           # Python version
cpu_only = true                   # Use --cpu flag (no GPU needed)
timeout = 300                     # Setup timeout in seconds

[test.platforms]
linux = true                      # Test on Linux
windows = true                    # Test on Windows
windows_portable = true           # Test on Windows Portable

[test.verification]
expected_nodes = [                # Nodes that must exist after install
    "MyNode1",
    "MyNode2",
]

[test.workflow]
file = "tests/workflows/smoke.json"  # Workflow to run
timeout = 120                        # Workflow timeout

[test.windows_portable]
comfyui_portable_version = "latest"  # Portable version to download
```

## CLI

```bash
# Install
pip install comfy-test

# Show config
comfy-test info

# Run tests locally
comfy-test run --platform linux

# Dry run (show what would happen)
comfy-test run --dry-run

# Generate GitHub workflow
comfy-test init-ci
```

## License

MIT
