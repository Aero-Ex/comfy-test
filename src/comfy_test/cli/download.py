"""Download commands for comfy-test CLI."""

import platform as plat
import sys
from pathlib import Path


def cmd_download_portable(args) -> int:
    """Download ComfyUI Portable for testing."""
    from ..platforms.windows_portable.platform import WindowsPortablePlatform

    platform = WindowsPortablePlatform()

    version = args.version
    if version == "latest":
        version = platform._get_latest_release_tag()

    output_path = Path(args.output)
    archive_path = output_path / f"ComfyUI_portable_{version}.7z"

    output_path.mkdir(parents=True, exist_ok=True)
    platform._download_portable(version, archive_path)

    print(f"Downloaded to: {archive_path}")
    return 0


def cmd_build_windows_image(args) -> int:
    """Build the Windows base image for faster local testing."""
    if plat.system() != "Windows":
        print("Error: This command only works on Windows", file=sys.stderr)
        return 1

    from ..github.local_runner import build_windows_base_image

    try:
        image_name = build_windows_base_image(print, force=args.rebuild)
        print(f"\nBase image ready: {image_name}")
        print("Subsequent 'ct test' runs will use this image for fast startup.")
        return 0
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1


def add_download_parser(subparsers):
    """Add the download-portable subcommand parser."""
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


def add_build_windows_image_parser(subparsers):
    """Add the build-windows-image subcommand parser."""
    build_win_parser = subparsers.add_parser(
        "build-windows-image",
        help="Build the Windows base image for faster local testing",
    )
    build_win_parser.add_argument(
        "--rebuild", "-r",
        action="store_true",
        help="Force rebuild even if image exists",
    )
    build_win_parser.set_defaults(func=cmd_build_windows_image)
