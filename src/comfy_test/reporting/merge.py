"""Merge test results from multiple runs.

This module handles merging results from different environments (e.g., CI without GPU
and local with GPU) so that gh-pages shows combined results.

The merge strategy:
- New results overwrite old results for workflows that actually ran
- Skipped workflows (status="skipped") preserve existing results from previous runs
- Screenshots/videos for preserved workflows are kept
"""

import json
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional, Dict, Any
from urllib.request import urlopen
from urllib.error import URLError


def fetch_existing_results(repo: str, branch: str = "gh-pages") -> Optional[Dict[str, Any]]:
    """Fetch existing results.json from gh-pages.

    Args:
        repo: GitHub repo in format "owner/repo"
        branch: Branch name (default: gh-pages)

    Returns:
        Parsed results.json or None if not found
    """
    # Try raw GitHub URL first
    url = f"https://raw.githubusercontent.com/{repo}/{branch}/results.json"
    try:
        with urlopen(url, timeout=10) as response:
            return json.loads(response.read().decode())
    except (URLError, json.JSONDecodeError):
        pass

    # Try GitHub Pages URL
    owner, name = repo.split("/")
    url = f"https://{owner}.github.io/{name}/results.json"
    try:
        with urlopen(url, timeout=10) as response:
            return json.loads(response.read().decode())
    except (URLError, json.JSONDecodeError):
        pass

    return None


def clone_gh_pages(repo: str, target_dir: Path) -> bool:
    """Clone gh-pages branch to get existing assets.

    Args:
        repo: GitHub repo in format "owner/repo"
        target_dir: Directory to clone into

    Returns:
        True if successful, False otherwise
    """
    try:
        result = subprocess.run(
            ["git", "clone", "--depth=1", "--branch=gh-pages",
             f"https://github.com/{repo}.git", str(target_dir)],
            capture_output=True, timeout=60
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def merge_results(
    new_results: Dict[str, Any],
    old_results: Optional[Dict[str, Any]],
) -> Dict[str, Any]:
    """Merge new results with old results.

    Strategy:
    - Workflows that ran (status != "skipped") use new results
    - Skipped workflows keep old results if available
    - Updates timestamp and summary

    Args:
        new_results: Results from current run
        old_results: Results from previous run (or None)

    Returns:
        Merged results
    """
    if not old_results:
        return new_results

    # Build lookup of old workflows by name
    old_workflows = {w["name"]: w for w in old_results.get("workflows", [])}

    # Merge workflows
    merged_workflows = []
    for new_wf in new_results.get("workflows", []):
        name = new_wf["name"]

        if new_wf.get("status") == "skipped" and name in old_workflows:
            # Keep old result for skipped workflow
            merged_workflows.append(old_workflows[name])
        else:
            # Use new result
            merged_workflows.append(new_wf)

    # Add any old workflows not in new results (shouldn't happen normally)
    new_names = {w["name"] for w in new_results.get("workflows", [])}
    for old_wf in old_results.get("workflows", []):
        if old_wf["name"] not in new_names:
            merged_workflows.append(old_wf)

    # Recalculate summary
    passed = sum(1 for w in merged_workflows if w.get("status") == "pass")
    failed = sum(1 for w in merged_workflows if w.get("status") == "fail")
    skipped = sum(1 for w in merged_workflows if w.get("status") == "skipped")

    return {
        "timestamp": new_results.get("timestamp"),
        "platform": new_results.get("platform"),
        "summary": {
            "total": len(merged_workflows),
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
        },
        "workflows": merged_workflows,
    }


def merge_assets(
    output_dir: Path,
    old_gh_pages_dir: Path,
    new_results: Dict[str, Any],
) -> None:
    """Copy assets for preserved (skipped) workflows from old gh-pages.

    Args:
        output_dir: Directory with new results
        old_gh_pages_dir: Directory with cloned gh-pages
        new_results: Results from current run (to identify skipped workflows)
    """
    skipped_names = {
        w["name"] for w in new_results.get("workflows", [])
        if w.get("status") == "skipped"
    }

    if not skipped_names:
        return

    # Copy screenshots for skipped workflows
    old_screenshots = old_gh_pages_dir / "screenshots"
    new_screenshots = output_dir / "screenshots"
    if old_screenshots.exists():
        new_screenshots.mkdir(parents=True, exist_ok=True)
        for name in skipped_names:
            # Try both _executed.png and .png suffixes
            for suffix in ["_executed.png", ".png"]:
                old_file = old_screenshots / f"{name}{suffix}"
                if old_file.exists():
                    new_file = new_screenshots / f"{name}{suffix}"
                    if not new_file.exists():
                        shutil.copy2(old_file, new_file)

    # Copy video folders for skipped workflows
    old_videos = old_gh_pages_dir / "videos"
    new_videos = output_dir / "videos"
    if old_videos.exists():
        new_videos.mkdir(parents=True, exist_ok=True)
        for name in skipped_names:
            old_video_dir = old_videos / name
            new_video_dir = new_videos / name
            if old_video_dir.exists() and not new_video_dir.exists():
                shutil.copytree(old_video_dir, new_video_dir)

    # Copy logs for skipped workflows
    old_logs = old_gh_pages_dir / "logs"
    new_logs = output_dir / "logs"
    if old_logs.exists():
        new_logs.mkdir(parents=True, exist_ok=True)
        for name in skipped_names:
            old_file = old_logs / f"{name}.log"
            if old_file.exists():
                new_file = new_logs / f"{name}.log"
                if not new_file.exists():
                    shutil.copy2(old_file, new_file)


def merge_with_gh_pages(
    output_dir: Path,
    repo: str,
    log_callback=None,
) -> bool:
    """Merge current results with existing gh-pages results.

    This is the main entry point. It:
    1. Fetches existing results.json from gh-pages
    2. Clones gh-pages to get existing assets
    3. Merges results (skipped workflows keep old data)
    4. Copies assets for preserved workflows
    5. Writes merged results.json

    Args:
        output_dir: Directory with current test results
        repo: GitHub repo in format "owner/repo"
        log_callback: Optional logging callback

    Returns:
        True if merge was performed, False if no existing results
    """
    log = log_callback or print

    results_file = output_dir / "results.json"
    if not results_file.exists():
        log("No results.json found, nothing to merge")
        return False

    new_results = json.loads(results_file.read_text())

    # Check if we have any skipped workflows
    skipped = [w for w in new_results.get("workflows", []) if w.get("status") == "skipped"]
    if not skipped:
        log("No skipped workflows, nothing to merge")
        return False

    log(f"Found {len(skipped)} skipped workflow(s), fetching existing results...")

    # Fetch existing results
    old_results = fetch_existing_results(repo)
    if not old_results:
        log("No existing results on gh-pages, skipping merge")
        return False

    log(f"Found existing results with {len(old_results.get('workflows', []))} workflow(s)")

    # Clone gh-pages to get assets
    with tempfile.TemporaryDirectory() as tmp:
        tmp_dir = Path(tmp) / "gh-pages"
        log("Cloning gh-pages for assets...")
        if clone_gh_pages(repo, tmp_dir):
            # Merge assets first (before overwriting results.json)
            merge_assets(output_dir, tmp_dir, new_results)
            log("Merged assets for skipped workflows")
        else:
            log("Could not clone gh-pages, skipping asset merge")

    # Merge results
    merged = merge_results(new_results, old_results)

    # Write merged results
    results_file.write_text(json.dumps(merged, indent=2))
    log(f"Merged results: {merged['summary']['passed']} passed, {merged['summary']['failed']} failed, {merged['summary'].get('skipped', 0)} skipped")

    return True
