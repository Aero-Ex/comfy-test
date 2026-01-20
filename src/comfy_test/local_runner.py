"""Local test execution via act (GitHub Actions locally)."""

import subprocess
import shutil
import time
import re
import sys
from pathlib import Path
from typing import Callable, Optional, List, Tuple

ACT_IMAGE = "catthehacker/ubuntu:act-22.04"

# Patterns to detect step transitions in act output
STEP_START = re.compile(r'^Run (?:Main |Post )?(.+)$')
STEP_SUCCESS = re.compile(r'^Success - (?:Main |Post )?(.+?) \[')
STEP_FAILURE = re.compile(r'^Failure - (?:Main |Post )?(.+?) \[')


def split_log_by_workflow(log_file: Path, logs_dir: Path) -> int:
    """Extract per-workflow sections from main log file."""
    if not log_file.exists():
        return 0

    content = log_file.read_text()
    lines = content.splitlines()

    workflow_start = re.compile(r'\[\d+/\d+\] RUNNING.*?(\S+)\.json')
    workflow_end = re.compile(r'Status: (success|FAILED)')

    logs_dir.mkdir(parents=True, exist_ok=True)

    current_workflow = None
    current_lines = []
    count = 0

    for line in lines:
        match = workflow_start.search(line)
        if match:
            if current_workflow and current_lines:
                (logs_dir / f"{current_workflow}.log").write_text("\n".join(current_lines))
                count += 1
            current_workflow = match.group(1)
            current_lines = [line]
        elif current_workflow:
            current_lines.append(line)
            if workflow_end.search(line):
                (logs_dir / f"{current_workflow}.log").write_text("\n".join(current_lines))
                count += 1
                current_workflow = None
                current_lines = []

    return count


def run_local(
    node_dir: Path,
    output_dir: Path,
    config_file: str = "comfy-test.toml",
    gpu: bool = False,
    verbose: bool = False,
    log_callback: Optional[Callable[[str], None]] = None,
) -> int:
    """Run tests locally via act (GitHub Actions in Docker).

    Args:
        node_dir: Path to the custom node directory
        output_dir: Where to save screenshots/logs/results.json
        config_file: Config file name
        gpu: Enable GPU passthrough
        verbose: Show all output (streaming mode)
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

    # Create main log file (sibling to output_dir, not inside it)
    log_file = output_dir.parent / f"{output_dir.name}.log"

    # Set up local workflow with test-matrix-local.yml
    local_comfy_test = Path.home() / "utils" / "comfy-test"
    local_workflow = local_comfy_test / ".github" / "workflows" / "test-matrix-local.yml"

    if local_workflow.exists():
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
        "stdbuf", "-oL",
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

    # Track steps for summary mode
    current_step = None
    current_step_output: List[str] = []
    completed_steps: List[Tuple[str, bool, List[str]]] = []

    try:
        with open(log_file, "w") as f:
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
                        formatted = f"{timer} {clean_line}"

                        # Always write to log file
                        f.write(formatted + "\n")
                        f.flush()

                        if verbose:
                            # Verbose mode: stream everything
                            log(formatted)
                        else:
                            # Summary mode: track steps
                            if match := STEP_START.search(clean_line):
                                current_step = match.group(1)
                                current_step_output = []
                                # Print step name without newline
                                sys.stdout.write(f"  {current_step}... ")
                                sys.stdout.flush()
                            elif match := STEP_SUCCESS.search(clean_line):
                                step_name = match.group(1)
                                print("[OK]")
                                completed_steps.append((step_name, True, []))
                                current_step = None
                            elif match := STEP_FAILURE.search(clean_line):
                                step_name = match.group(1)
                                print("[ERROR]")
                                completed_steps.append((step_name, False, current_step_output.copy()))
                                current_step = None

                            # Capture output for error context
                            if current_step and clean_line.strip():
                                current_step_output.append(clean_line)
                                if len(current_step_output) > 20:
                                    current_step_output.pop(0)
                    elif process.poll() is not None:
                        break
                else:
                    break
    except KeyboardInterrupt:
        process.kill()
        process.wait()
        subprocess.run(
            f"docker kill $(docker ps -q --filter ancestor={ACT_IMAGE}) 2>/dev/null",
            shell=True,
            capture_output=True,
        )
        log("\nTest cancelled")
        return 130

    # Show error context for failed steps
    if not verbose:
        for step_name, success, output in completed_steps:
            if not success and output:
                log(f"\n  Error in {step_name}:")
                for line in output[-5:]:
                    log(f"    {line}")

    # Split main log into per-workflow logs
    logs_dir = output_dir / "logs"
    if logs_dir.exists():
        subprocess.run(["sudo", "rm", "-rf", str(logs_dir)], capture_output=True)
    workflow_logs = split_log_by_workflow(log_file, logs_dir)

    # Report output
    screenshots_dir = output_dir / "screenshots"
    screenshot_files = list(screenshots_dir.glob("*.png")) if screenshots_dir.exists() else []
    results_file = output_dir / "results.json"

    if screenshot_files or results_file.exists() or log_file.exists():
        log(f"\nLog: {log_file}")
        if workflow_logs:
            log(f"Workflow logs: {workflow_logs}")
        if screenshot_files:
            log(f"Screenshots: {len(screenshot_files)}")

    return process.returncode or 0
