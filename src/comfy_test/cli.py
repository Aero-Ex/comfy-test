"""CLI for comfy-test."""

import argparse
import sys
from pathlib import Path

from .test.config import TestLevel
from .test.config_file import discover_config, load_config, CONFIG_FILE_NAMES
from .test.manager import TestManager
from .test.node_discovery import discover_nodes
from .errors import TestError, ConfigError, SetupError


def cmd_run(args) -> int:
    """Run installation tests."""
    try:
        # Load config
        if args.config:
            config = load_config(args.config)
        else:
            config = discover_config()

        # Parse level if specified
        level = None
        if args.level:
            level = TestLevel(args.level)

        # Create manager
        manager = TestManager(config)

        # Run tests
        if args.platform:
            results = [manager.run_platform(args.platform, args.dry_run, level)]
        else:
            results = manager.run_all(args.dry_run, level)

        # Report results
        print(f"\n{'='*60}")
        print("RESULTS")
        print(f"{'='*60}")

        all_passed = True
        for result in results:
            status = "PASS" if result.success else "FAIL"
            print(f"  {result.platform}: {status}")
            if not result.success:
                all_passed = False
                if result.error:
                    print(f"    Error: {result.error}")

        return 0 if all_passed else 1

    except ConfigError as e:
        print(f"Configuration error: {e.message}", file=sys.stderr)
        if e.details:
            print(f"Details: {e.details}", file=sys.stderr)
        return 1
    except TestError as e:
        print(f"Test error: {e.message}", file=sys.stderr)
        return 1


def cmd_verify(args) -> int:
    """Verify node registration only."""
    try:
        if args.config:
            config = load_config(args.config)
        else:
            config = discover_config()

        manager = TestManager(config)
        results = manager.verify_only(args.platform)

        all_passed = all(r.success for r in results)
        for result in results:
            status = "PASS" if result.success else "FAIL"
            print(f"{result.platform}: {status}")
            if not result.success and result.error:
                print(f"  Error: {result.error}")

        return 0 if all_passed else 1

    except (ConfigError, TestError) as e:
        print(f"Error: {e.message}", file=sys.stderr)
        return 1


def cmd_info(args) -> int:
    """Show configuration and environment info."""
    try:
        if args.config:
            config = load_config(args.config)
            config_path = args.config
        else:
            try:
                config = discover_config()
                config_path = "auto-discovered"
            except ConfigError:
                print("No configuration file found.")
                print(f"Searched for: {', '.join(CONFIG_FILE_NAMES)}")
                return 1

        print(f"Configuration: {config_path}")
        print(f"  Name: {config.name}")
        print(f"  ComfyUI Version: {config.comfyui_version}")
        print(f"  Python Version: {config.python_version}")
        print(f"  CPU Only: {config.cpu_only}")
        print(f"  Timeout: {config.timeout}s")
        print()
        print("Platforms:")
        print(f"  Linux: {'enabled' if config.linux.enabled else 'disabled'}")
        print(f"  Windows: {'enabled' if config.windows.enabled else 'disabled'}")
        print(f"  Windows Portable: {'enabled' if config.windows_portable.enabled else 'disabled'}")
        print()
        print("Nodes (auto-discovered from NODE_CLASS_MAPPINGS):")
        try:
            node_dir = Path(args.config).parent if args.config else Path.cwd()
            nodes = discover_nodes(node_dir)
            print(f"  Found {len(nodes)} node(s):")
            for node in nodes:
                print(f"    - {node}")
        except SetupError as e:
            print(f"  Error discovering nodes: {e.message}")
        print()
        print("Workflows:")
        if config.workflow.files:
            print(f"  Files ({len(config.workflow.files)}):")
            for wf in config.workflow.files:
                print(f"    - {wf}")
            print(f"  Timeout: {config.workflow.timeout}s")
        else:
            print("  No workflows configured")

        return 0

    except ConfigError as e:
        print(f"Error: {e.message}", file=sys.stderr)
        return 1


def cmd_init_ci(args) -> int:
    """Generate GitHub Actions workflow file."""
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    workflow_content = '''name: Test Installation
on: [push, pull_request]

jobs:
  test:
    uses: PozzettiAndrea/comfy-test/.github/workflows/test-matrix.yml@main
    with:
      config-file: "comfy-test.toml"
'''

    with open(output_path, "w") as f:
        f.write(workflow_content)

    print(f"Generated GitHub Actions workflow: {output_path}")
    print()
    print("Make sure to:")
    print("  1. Create a comfy-test.toml in your repository root")
    print("  2. Commit both files to your repository")
    print()
    print("Example comfy-test.toml:")
    print('''
[test]
name = "MyNode"
python_version = "3.10"

[test.workflows]
files = ["workflows/basic.json"]
timeout = 120
''')

    return 0


def cmd_download_portable(args) -> int:
    """Download ComfyUI Portable for testing."""
    from .test.platform.windows_portable import WindowsPortableTestPlatform

    platform = WindowsPortableTestPlatform()

    version = args.version
    if version == "latest":
        version = platform._get_latest_release_tag()

    output_path = Path(args.output)
    archive_path = output_path / f"ComfyUI_portable_{version}.7z"

    output_path.mkdir(parents=True, exist_ok=True)
    platform._download_portable(version, archive_path)

    print(f"Downloaded to: {archive_path}")
    return 0


def main(args=None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="comfy-test",
        description="Installation testing for ComfyUI custom nodes",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # run command
    run_parser = subparsers.add_parser(
        "run",
        help="Run installation tests",
    )
    run_parser.add_argument(
        "--config", "-c",
        help="Path to config file (default: auto-discover)",
    )
    run_parser.add_argument(
        "--platform", "-p",
        choices=["linux", "windows", "windows-portable"],
        help="Run on specific platform only",
    )
    run_parser.add_argument(
        "--level", "-l",
        choices=["install", "registration", "instantiation", "validation"],
        help="Stop at a specific test level (default: run all levels + workflows)",
    )
    run_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show what would be done without doing it",
    )
    run_parser.set_defaults(func=cmd_run)

    # verify command
    verify_parser = subparsers.add_parser(
        "verify",
        help="Verify node registration only",
    )
    verify_parser.add_argument(
        "--config", "-c",
        help="Path to config file",
    )
    verify_parser.add_argument(
        "--platform", "-p",
        choices=["linux", "windows", "windows-portable"],
        help="Platform to verify on",
    )
    verify_parser.set_defaults(func=cmd_verify)

    # info command
    info_parser = subparsers.add_parser(
        "info",
        help="Show configuration info",
    )
    info_parser.add_argument(
        "--config", "-c",
        help="Path to config file",
    )
    info_parser.set_defaults(func=cmd_info)

    # init-ci command
    init_ci_parser = subparsers.add_parser(
        "init-ci",
        help="Generate GitHub Actions workflow",
    )
    init_ci_parser.add_argument(
        "--output", "-o",
        default=".github/workflows/test-install.yml",
        help="Output file path",
    )
    init_ci_parser.set_defaults(func=cmd_init_ci)

    # download-portable command
    download_parser = subparsers.add_parser(
        "download-portable",
        help="Download ComfyUI Portable",
    )
    download_parser.add_argument(
        "--version", "-v",
        default="latest",
        help="Version to download (default: latest)",
    )
    download_parser.add_argument(
        "--output", "-o",
        default=".",
        help="Output directory",
    )
    download_parser.set_defaults(func=cmd_download_portable)

    parsed_args = parser.parse_args(args)
    return parsed_args.func(parsed_args)


if __name__ == "__main__":
    sys.exit(main())
