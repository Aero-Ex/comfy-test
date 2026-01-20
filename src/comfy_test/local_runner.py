"""Local test execution via act (GitHub Actions locally)."""

import subprocess
import shutil
import time
import re
from pathlib import Path
from typing import Callable, Optional

ACT_IMAGE = "catthehacker/ubuntu:act-22.04"


def run_local(
    node_dir: Path,
    output_dir: Path,
    config_file: str = "comfy-test.toml",
    gpu: bool = False,
    log_callback: Optional[Callable[[str], None]] = None,
) -> int:
    """Run tests locally via act (GitHub Actions in Docker).

    Args:
        node_dir: Path to the custom node directory
        output_dir: Where to save screenshots/logs/results.json
        config_file: Config file name
        gpu: Enable GPU passthrough
        log_callback: Function to call with log lines

    Returns:
        Exit code (0 = success)
    """
    log = log_callback or print

    # Verify act is installed
    if not shutil.which("act"):
        log("Error: act is not installed. Install from https://github.com/nektos/act")
        return 1

    # Verify node directory has config
    if not (node_dir / config_file).exists():
        log(f"Error: {config_file} not found in {node_dir}")
        return 1

    # Verify workflow file exists
    workflow_file = node_dir / ".github" / "workflows" / "comfy-test.yml"
    if not workflow_file.exists():
        log(f"Error: {workflow_file} not found")
        return 1

    # Create output directory
    output_dir.mkdir(parents=True, exist_ok=True)

    # Set up local workflow with test-matrix-local.yml
    local_comfy_test = Path.home() / "utils" / "comfy-test"
    local_workflow = local_comfy_test / ".github" / "workflows" / "test-matrix-local.yml"

    if local_workflow.exists():
        # Copy and modify workflow for unique job names
        node_workflow_dir = node_dir / ".github" / "workflows"
        node_workflow_dir.mkdir(parents=True, exist_ok=True)
        target = node_workflow_dir / "test-matrix.yml"

        workflow_content = local_workflow.read_text()
        repo_suffix = node_dir.name.replace("ComfyUI-", "").lower()
        workflow_content = workflow_content.replace("test-linux:", f"test-linux-{repo_suffix}:")
        workflow_content = workflow_content.replace("test-windows:", f"test-windows-{repo_suffix}:")

        if target.exists() or target.is_symlink():
            target.unlink()
        target.write_text(workflow_content)

        # Patch comfy-test.yml to use local workflow reference
        comfy_test_yml = node_workflow_dir / "comfy-test.yml"
        if comfy_test_yml.exists():
            content = comfy_test_yml.read_text()
            patched = re.sub(
                r'uses:\s*PozzettiAndrea/comfy-test/\.github/workflows/test-matrix\.yml@\w+',
                'uses: ./.github/workflows/test-matrix.yml',
                content
            )
            if patched != content:
                comfy_test_yml.write_text(patched)

    # Build container options
    local_comfy_env = Path.home() / "utils" / "comfy-env"
    container_opts = [
        f"-v {output_dir}:{node_dir}/.comfy-test",
        "--network bridge",
    ]
    if local_comfy_test.exists():
        container_opts.append(f"-v {local_comfy_test}:/local-comfy-test")
    if local_comfy_env.exists():
        container_opts.append(f"-v {local_comfy_env}:/local-comfy-env")
    if gpu:
        container_opts.append("--gpus all")

    # Build command
    cmd = [
        "stdbuf", "-oL",  # Force line buffering
        "act",
        "-P", f"ubuntu-latest={ACT_IMAGE}",
        "--pull=false",
        "--rm",
        "-j", "test",
        "--container-options", " ".join(container_opts),
        "--env", "PYTHONUNBUFFERED=1",
    ]
    if gpu:
        cmd.extend(["--env", "COMFY_TEST_GPU=1"])

    log(f"Running: {' '.join(cmd)}")
    log(f"Output: {output_dir}")

    # Patterns to strip from output
    emoji_pattern = re.compile(r'[⭐🚀🐳✅❌🏁⬇️📜✏️❓🧪🔧💬⚙️🚧☁️]')
    job_prefix_pattern = re.compile(r'\[test/[^\]]+\]\s*')

    start_time = time.time()

    # Run with unbuffered output
    process = subprocess.Popen(
        cmd,
        cwd=node_dir,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        bufsize=1,
        universal_newlines=True,
    )

    try:
        while True:
            if process.stdout:
                line = process.stdout.readline()
                if line:
                    # Strip noise: emojis and job prefix
                    clean_line = emoji_pattern.sub('', line.rstrip())
                    clean_line = job_prefix_pattern.sub('', clean_line)
                    elapsed = int(time.time() - start_time)
                    mins, secs = divmod(elapsed, 60)
                    timer = f"[{mins:02d}:{secs:02d}]"
                    log(f"{timer} {clean_line}")
                elif process.poll() is not None:
                    break
            else:
                break
    except KeyboardInterrupt:
        process.kill()
        process.wait()
        # Kill any orphaned act containers
        subprocess.run(
            f"docker kill $(docker ps -q --filter ancestor={ACT_IMAGE}) 2>/dev/null",
            shell=True,
            capture_output=True,
        )
        log("\nTest cancelled")
        return 130

    # Report output
    screenshots_dir = output_dir / "screenshots"
    screenshot_files = list(screenshots_dir.glob("*.png")) if screenshots_dir.exists() else []
    results_file = output_dir / "results.json"

    if screenshot_files or results_file.exists():
        log(f"\nOutput: {output_dir}")
        if screenshot_files:
            log(f"  Screenshots: {len(screenshot_files)}")
        if results_file.exists():
            log(f"  Results: results.json")
    else:
        # Clean up empty directory
        try:
            output_dir.rmdir()
        except OSError:
            pass

    return process.returncode or 0
