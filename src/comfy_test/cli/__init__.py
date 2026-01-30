"""CLI commands for comfy-test.

This module provides the command-line interface for comfy-test.
Commands are organized into separate modules for maintainability.
"""

import argparse
import sys

# Import command handlers from individual modules
from .run import cmd_run, add_run_parser
from .verify import cmd_verify, add_verify_parser
from .info import cmd_info, add_info_parser
from .init import cmd_init, cmd_init_ci, add_init_parser, add_init_ci_parser
from .download import cmd_download_portable, cmd_build_windows_image, add_download_parser, add_build_windows_image_parser
from .screenshot import cmd_screenshot, add_screenshot_parser
from .merge import cmd_merge, add_merge_parser
from .publish import cmd_publish, add_publish_parser
from .pool import cmd_pool, add_pool_parser
from .generate import cmd_generate_index, cmd_generate_root_index, add_generate_index_parser, add_generate_root_index_parser


def main(args=None) -> int:
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        prog="comfy-test",
        description="Installation testing for ComfyUI custom nodes",
    )
    subparsers = parser.add_subparsers(dest="command", required=True)

    # Register all commands
    add_run_parser(subparsers)
    add_verify_parser(subparsers)
    add_info_parser(subparsers)
    add_init_parser(subparsers)
    add_init_ci_parser(subparsers)
    add_download_parser(subparsers)
    add_screenshot_parser(subparsers)
    add_merge_parser(subparsers)
    add_publish_parser(subparsers)
    add_pool_parser(subparsers)
    add_generate_index_parser(subparsers)
    add_generate_root_index_parser(subparsers)
    add_build_windows_image_parser(subparsers)

    # Parse and execute
    parsed_args = parser.parse_args(args)
    return parsed_args.func(parsed_args)


if __name__ == "__main__":
    sys.exit(main())
