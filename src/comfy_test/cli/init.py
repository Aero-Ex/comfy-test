"""Init commands for comfy-test CLI."""

import shutil
import sys
from importlib.resources import files
from pathlib import Path


def cmd_init(args) -> int:
    """Handle init command - copy template files."""
    cwd = Path.cwd()
    config_path = cwd / "comfy-test.toml"
    github_dir = cwd / ".github"

    # Get templates directory from package root (moved to project root)
    # Try package resources first, fall back to relative path
    try:
        templates = files("comfy_test") / "templates"
    except (TypeError, FileNotFoundError):
        # Fallback: templates at project root
        templates = Path(__file__).parent.parent.parent.parent / "templates"

    # Check existing files
    if not args.force:
        if config_path.exists():
            print(f"Config file already exists: {config_path}", file=sys.stderr)
            print("Use --force to overwrite", file=sys.stderr)
            return 1

    # Copy comfy-test.toml
    template_config = templates / "comfy-test.toml"
    shutil.copy(template_config, config_path)
    print(f"Created {config_path}")

    # Copy github/ -> .github/
    template_github = templates / "github"
    if template_github.is_dir():
        shutil.copytree(template_github, github_dir, dirs_exist_ok=True)
        print(f"Created {github_dir}/")

    return 0


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
    return 0


def add_init_parser(subparsers):
    """Add the init subcommand parser."""
    init_parser = subparsers.add_parser(
        "init",
        help="Create a default comfy-test.toml config file",
    )
    init_parser.add_argument(
        "--force", "-f",
        action="store_true",
        help="Overwrite existing config file",
    )
    init_parser.set_defaults(func=cmd_init)


def add_init_ci_parser(subparsers):
    """Add the init-ci subcommand parser."""
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
