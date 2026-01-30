"""Report generation commands for comfy-test CLI."""

import sys
from pathlib import Path


def cmd_generate_index(args) -> int:
    """Generate index.html with platform tabs for a single branch/directory."""
    from ..reporting.html_report import generate_root_index

    output_dir = Path(args.output_dir)
    if not output_dir.exists():
        print(f"Output directory not found: {output_dir}", file=sys.stderr)
        return 1

    index_file = generate_root_index(output_dir, args.repo_name)
    print(f"Generated: {index_file}")
    return 0


def cmd_generate_root_index(args) -> int:
    """Generate root index.html with branch switcher tabs."""
    from ..reporting.html_report import generate_branch_root_index

    output_dir = Path(args.output_dir)
    if not output_dir.exists():
        print(f"Output directory not found: {output_dir}", file=sys.stderr)
        return 1

    index_file = generate_branch_root_index(output_dir, args.repo_name)
    print(f"Generated: {index_file}")
    return 0


def add_generate_index_parser(subparsers):
    """Add the generate-index subcommand parser."""
    generate_index_parser = subparsers.add_parser(
        "generate-index",
        help="Generate index.html with platform tabs for a single branch directory",
    )
    generate_index_parser.add_argument(
        "output_dir",
        help="Directory containing platform subdirectories (e.g., gh-pages/main)",
    )
    generate_index_parser.add_argument(
        "--repo-name", "-r",
        help="Repository name for the header (e.g., owner/repo)",
    )
    generate_index_parser.set_defaults(func=cmd_generate_index)


def add_generate_root_index_parser(subparsers):
    """Add the generate-root-index subcommand parser."""
    generate_root_index_parser = subparsers.add_parser(
        "generate-root-index",
        help="Generate root index.html with branch switcher for gh-pages",
    )
    generate_root_index_parser.add_argument(
        "output_dir",
        help="Root gh-pages directory containing branch subdirectories (main/, dev/, etc.)",
    )
    generate_root_index_parser.add_argument(
        "--repo-name", "-r",
        help="Repository name for the header (e.g., owner/repo)",
    )
    generate_root_index_parser.set_defaults(func=cmd_generate_root_index)
