"""Merge commands for comfy-test CLI."""

import sys
from pathlib import Path


def cmd_merge(args) -> int:
    """Merge results with existing gh-pages."""
    from ..reporting.merge import merge_with_gh_pages

    output_dir = Path(args.output_dir)
    if not output_dir.exists():
        print(f"Output directory not found: {output_dir}", file=sys.stderr)
        return 1

    success = merge_with_gh_pages(output_dir, args.repo, log_callback=print)
    return 0 if success else 1


def add_merge_parser(subparsers):
    """Add the merge subcommand parser."""
    merge_parser = subparsers.add_parser(
        "merge",
        help="Merge results with existing gh-pages (for combining CI and local GPU runs)",
    )
    merge_parser.add_argument(
        "repo",
        help="GitHub repo in format 'owner/repo'",
    )
    merge_parser.add_argument(
        "--output-dir", "-o",
        default="comfy-test-results",
        help="Directory with test results (default: comfy-test-results)",
    )
    merge_parser.set_defaults(func=cmd_merge)
