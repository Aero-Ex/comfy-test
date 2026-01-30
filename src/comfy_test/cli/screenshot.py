"""Screenshot commands for comfy-test CLI."""

import sys
import tempfile
from pathlib import Path

from ..common.config_file import discover_config, load_config
from ..common.errors import TestError, ConfigError


def cmd_screenshot(args) -> int:
    """Generate workflow screenshots."""
    try:
        # Import screenshot module (requires optional dependencies)
        try:
            from ..reporting.screenshot import (
                WorkflowScreenshot,
                check_dependencies,
                ScreenshotError,
            )
            from ..reporting.screenshot_cache import ScreenshotCache
            check_dependencies()
        except ImportError as e:
            print(f"Error: {e}", file=sys.stderr)
            print("Install with: pip install comfy-test[screenshot]", file=sys.stderr)
            return 1

        # Load config to get workflow files
        if args.config:
            config = load_config(args.config)
            node_dir = Path(args.config).parent
        else:
            try:
                config = discover_config()
                node_dir = Path.cwd()
            except ConfigError:
                config = None
                node_dir = Path.cwd()

        # Determine which workflows to capture
        workflow_files = []

        if args.workflow:
            # Specific workflow provided
            workflow_path = Path(args.workflow)
            if not workflow_path.is_absolute():
                workflow_path = node_dir / workflow_path
            workflow_files = [workflow_path]
        elif config and config.workflow.workflows:
            # Use workflows from config
            workflow_files = config.workflow.workflows
        else:
            # Auto-discover from workflows/ directory
            workflows_dir = node_dir / "workflows"
            if workflows_dir.exists():
                workflow_files = sorted(workflows_dir.glob("*.json"))

        if not workflow_files:
            print("No workflow files found.", file=sys.stderr)
            print("Specify a workflow file or configure workflows in comfy-test.toml", file=sys.stderr)
            return 1

        # Determine output directory
        output_dir = Path(args.output) if args.output else None

        # Initialize cache
        cache = ScreenshotCache(node_dir)

        # Filter workflows that need updating (unless --force)
        def get_output_path(wf: Path) -> Path:
            if output_dir:
                if args.execute:
                    return output_dir / wf.with_stem(wf.stem + "_executed").with_suffix(".png").name
                return output_dir / wf.with_suffix(".png").name
            if args.execute:
                return wf.with_stem(wf.stem + "_executed").with_suffix(".png")
            return wf.with_suffix(".png")

        if args.force:
            workflows_to_capture = workflow_files
            skipped = []
        else:
            workflows_to_capture = []
            skipped = []
            for wf in workflow_files:
                out_path = get_output_path(wf)
                if cache.needs_update(wf, out_path):
                    workflows_to_capture.append(wf)
                else:
                    skipped.append(wf)

        # Determine server URL
        if args.server is True:
            # --server flag without URL, use default
            server_url = "http://localhost:8188"
            use_existing_server = True
        elif args.server:
            # --server with custom URL
            server_url = args.server
            use_existing_server = True
        else:
            # No --server flag, need to start our own server
            server_url = "http://127.0.0.1:8188"
            use_existing_server = False

        # Dry run mode
        if args.dry_run:
            if skipped:
                print(f"Skipping {len(skipped)} unchanged workflow(s):")
                for wf in skipped:
                    print(f"  {wf.name} (cached)")
            if workflows_to_capture:
                print(f"Would capture {len(workflows_to_capture)} screenshot(s):")
                for wf in workflows_to_capture:
                    out_path = get_output_path(wf)
                    print(f"  {wf} -> {out_path}")
            else:
                print("All screenshots up to date.")
            if use_existing_server and workflows_to_capture:
                print(f"Using existing server at: {server_url}")
            elif workflows_to_capture:
                print("Would start ComfyUI server for screenshots")
            return 0

        # Log function
        def log(msg: str) -> None:
            print(msg)

        # Report skipped workflows
        if skipped:
            log(f"Skipping {len(skipped)} unchanged workflow(s)")

        if not workflows_to_capture:
            log("All screenshots up to date.")
            return 0

        # Capture screenshots
        results = []

        if use_existing_server:
            # Connect to existing server
            log(f"Connecting to existing server at {server_url}...")
            with WorkflowScreenshot(server_url, log_callback=log) as ws:
                for wf in workflows_to_capture:
                    out_path = get_output_path(wf)
                    try:
                        if args.execute:
                            result = ws.capture_after_execution(
                                wf, out_path, timeout=args.timeout
                            )
                        else:
                            result = ws.capture(wf, out_path)
                        cache.save_fingerprint(wf, out_path)
                        results.append(result)
                    except ScreenshotError as e:
                        log(f"  ERROR: {e.message}")
        else:
            # Start our own server (requires full test environment)
            if not config:
                print("Error: No config file found.", file=sys.stderr)
                print("Use --server to connect to an existing ComfyUI server,", file=sys.stderr)
                print("or create a comfy-test.toml config file.", file=sys.stderr)
                return 1

            log("Setting up ComfyUI environment for screenshots...")
            from ..orchestration.manager import get_platform
            from ..common.comfy_env import get_cuda_packages
            from ..comfyui.server import ComfyUIServer

            platform = get_platform(log_callback=log)

            with tempfile.TemporaryDirectory(prefix="comfy_screenshot_") as work_dir:
                work_path = Path(work_dir)

                # Setup ComfyUI
                log("Setting up ComfyUI...")
                paths = platform.setup_comfyui(config, work_path)

                # Install the node
                log("Installing custom node...")
                platform.install_node(paths, node_dir)

                # Get CUDA packages to mock
                cuda_packages = get_cuda_packages(node_dir)

                # Start server
                log("Starting ComfyUI server...")
                with ComfyUIServer(
                    platform, paths, config,
                    cuda_mock_packages=cuda_packages,
                    log_callback=log,
                ) as server:
                    with WorkflowScreenshot(server.base_url, log_callback=log) as ws:
                        for wf in workflows_to_capture:
                            out_path = get_output_path(wf)
                            try:
                                if args.execute:
                                    result = ws.capture_after_execution(
                                        wf, out_path, timeout=args.timeout
                                    )
                                else:
                                    result = ws.capture(wf, out_path)
                                cache.save_fingerprint(wf, out_path)
                                results.append(result)
                            except ScreenshotError as e:
                                log(f"  ERROR: {e.message}")

        # Report results
        print(f"\nCaptured {len(results)} screenshot(s)")
        for path in results:
            print(f"  {path}")

        return 0

    except ScreenshotError as e:
        print(f"Screenshot error: {e.message}", file=sys.stderr)
        if e.details:
            print(f"Details: {e.details}", file=sys.stderr)
        return 1
    except (ConfigError, TestError) as e:
        print(f"Error: {e.message}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        return 1


def add_screenshot_parser(subparsers):
    """Add the screenshot subcommand parser."""
    screenshot_parser = subparsers.add_parser(
        "screenshot",
        help="Generate workflow screenshots with embedded metadata",
    )
    screenshot_parser.add_argument(
        "workflow",
        nargs="?",
        help="Specific workflow file to screenshot (default: all from config)",
    )
    screenshot_parser.add_argument(
        "--config", "-c",
        help="Path to config file",
    )
    screenshot_parser.add_argument(
        "--output", "-o",
        help="Output directory for screenshots (default: same as workflow)",
    )
    screenshot_parser.add_argument(
        "--server", "-s",
        nargs="?",
        const=True,
        default=False,
        help="Use existing ComfyUI server (default: localhost:8188, or specify URL)",
    )
    screenshot_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be captured without doing it",
    )
    screenshot_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Force regeneration, ignoring cache",
    )
    screenshot_parser.add_argument(
        "--execute", "-e",
        action="store_true",
        help="Execute workflows before capturing (shows preview outputs)",
    )
    screenshot_parser.add_argument(
        "--timeout", "-t",
        type=int,
        default=300,
        help="Execution timeout in seconds (default: 300, only used with --execute)",
    )
    screenshot_parser.set_defaults(func=cmd_screenshot)
