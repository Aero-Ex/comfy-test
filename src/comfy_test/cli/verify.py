"""Verify command for comfy-test CLI."""

import sys

from ..common.config_file import discover_config, load_config
from ..common.errors import TestError, ConfigError


def cmd_verify(args) -> int:
    """Verify node registration only."""
    from ..orchestration.manager import TestManager

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


def add_verify_parser(subparsers):
    """Add the verify subcommand parser."""
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
        choices=["linux", "macos", "windows", "windows-portable"],
        help="Platform to verify on",
    )
    verify_parser.set_defaults(func=cmd_verify)
