"""Info command for comfy-test CLI."""

import sys

from ..common.config_file import discover_config, load_config, CONFIG_FILE_NAMES
from ..common.errors import ConfigError


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
        print(f"  Timeout: {config.timeout}s")
        print(f"  Levels: {', '.join(l.value for l in config.levels)}")
        print()
        print("Platforms:")
        print(f"  Linux: {'enabled' if config.linux.enabled else 'disabled'}")
        print(f"  Windows: {'enabled' if config.windows.enabled else 'disabled'}")
        print(f"  Windows Portable: {'enabled' if config.windows_portable.enabled else 'disabled'}")
        print()
        print("Workflows:")
        print(f"  Timeout: {config.workflow.timeout}s")
        if config.workflow.workflows:
            print(f"  Discovered: {len(config.workflow.workflows)} workflow(s)")
            for wf in config.workflow.workflows:
                print(f"    - {wf.name}")
        else:
            print("  Discovered: none")
        if config.workflow.gpu:
            print(f"  GPU required: {len(config.workflow.gpu)} workflow(s)")
            for wf in config.workflow.gpu:
                print(f"    - {wf.name}")

        return 0

    except ConfigError as e:
        print(f"Error: {e.message}", file=sys.stderr)
        return 1


def add_info_parser(subparsers):
    """Add the info subcommand parser."""
    info_parser = subparsers.add_parser(
        "info",
        help="Show configuration info",
    )
    info_parser.add_argument(
        "--config", "-c",
        help="Path to config file",
    )
    info_parser.set_defaults(func=cmd_info)
