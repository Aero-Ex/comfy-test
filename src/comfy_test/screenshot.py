"""Workflow screenshot capture using headless browser."""

import json
import subprocess
import sys
import tempfile
import requests
from pathlib import Path
from typing import Optional, Callable, TYPE_CHECKING

try:
    from playwright.sync_api import sync_playwright, Page, Browser
    PLAYWRIGHT_AVAILABLE = True
except ImportError:
    PLAYWRIGHT_AVAILABLE = False

try:
    from PIL import Image, PngImagePlugin
    PIL_AVAILABLE = True
except ImportError:
    PIL_AVAILABLE = False

from .errors import TestError

if TYPE_CHECKING:
    from .test.platform.base import TestPaths, TestPlatform
    from .test.config import TestConfig


class ScreenshotError(TestError):
    """Error during screenshot capture."""
    pass


def check_dependencies() -> None:
    """Check that required dependencies are installed.

    Raises:
        ImportError: If playwright or PIL is not installed
    """
    if not PLAYWRIGHT_AVAILABLE:
        raise ImportError(
            "Playwright is required for screenshots. "
            "Install it with: pip install comfy-test[screenshot]"
        )
    if not PIL_AVAILABLE:
        raise ImportError(
            "Pillow is required for screenshots. "
            "Install it with: pip install comfy-test[screenshot]"
        )


def ensure_dependencies(
    python_path: Optional[Path] = None,
    log_callback: Optional[Callable[[str], None]] = None,
) -> bool:
    """Ensure screenshot dependencies are installed, installing if needed.

    Automatically installs playwright and pillow if they are not available,
    then downloads the chromium browser for playwright.

    Args:
        python_path: Path to Python interpreter to install into.
                     If None, uses current interpreter.
        log_callback: Optional callback for logging messages.

    Returns:
        True if dependencies are available (or were successfully installed),
        False if installation failed.
    """
    global PLAYWRIGHT_AVAILABLE, PIL_AVAILABLE
    global sync_playwright, Page, Browser, Image, PngImagePlugin

    log = log_callback or (lambda msg: print(msg))

    # Check if already available
    if PLAYWRIGHT_AVAILABLE and PIL_AVAILABLE:
        return True

    log("Installing screenshot dependencies (playwright, pillow)...")

    python = str(python_path) if python_path else sys.executable

    try:
        # Install playwright and pillow
        result = subprocess.run(
            [python, "-m", "pip", "install", "playwright", "pillow"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            log(f"  Failed to install packages: {result.stderr}")
            return False

        log("  Packages installed, downloading chromium browser...")

        # Install chromium browser (required for playwright to work)
        result = subprocess.run(
            [python, "-m", "playwright", "install", "chromium"],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0:
            log(f"  Failed to install chromium: {result.stderr}")
            return False

        log("  Screenshot dependencies installed successfully")

        # If we installed to a different Python environment, we can't verify
        # via import in the current process - just trust the subprocess succeeded
        if python_path:
            return True

        # Update availability flags and import globals (only for current env)
        # We need to set the global names so WorkflowScreenshot can use them
        try:
            from playwright.sync_api import sync_playwright, Page, Browser
            PLAYWRIGHT_AVAILABLE = True
        except ImportError:
            pass

        try:
            from PIL import Image, PngImagePlugin
            PIL_AVAILABLE = True
        except ImportError:
            pass

        return PLAYWRIGHT_AVAILABLE and PIL_AVAILABLE

    except Exception as e:
        log(f"  Error installing dependencies: {e}")
        return False


class WorkflowScreenshot:
    """Captures screenshots of ComfyUI workflows with embedded metadata.

    Uses Playwright to render workflows in a headless browser and captures
    screenshots of the graph canvas. The workflow JSON is embedded in the
    PNG metadata so the image can be dragged back into ComfyUI.

    Args:
        server_url: URL of a running ComfyUI server
        width: Viewport width (default: 1920)
        height: Viewport height (default: 1080)
        log_callback: Optional callback for logging

    Example:
        >>> with WorkflowScreenshot("http://127.0.0.1:8188") as ws:
        ...     ws.capture(Path("workflow.json"), Path("workflow.png"))
    """

    def __init__(
        self,
        server_url: str = "http://127.0.0.1:8188",
        width: int = 1920,
        height: int = 1080,
        log_callback: Optional[Callable[[str], None]] = None,
    ):
        check_dependencies()

        self.server_url = server_url.rstrip("/")
        self.width = width
        self.height = height
        self._log = log_callback or (lambda msg: print(msg))
        self._playwright = None
        self._browser: Optional["Browser"] = None
        self._page: Optional["Page"] = None

    def start(self) -> None:
        """Start the headless browser."""
        if self._browser is not None:
            return

        self._log("Starting headless browser...")
        self._playwright = sync_playwright().start()
        self._browser = self._playwright.chromium.launch(headless=True)
        self._page = self._browser.new_page(
            viewport={"width": self.width, "height": self.height},
            device_scale_factor=2,  # HiDPI for crisp screenshots
        )


    def stop(self) -> None:
        """Stop the headless browser."""
        if self._page:
            self._page.close()
            self._page = None
        if self._browser:
            self._browser.close()
            self._browser = None
        if self._playwright:
            self._playwright.stop()
            self._playwright = None

    def _disable_first_run_tutorial(self) -> None:
        """Set server-side setting to prevent Templates panel from showing."""
        try:
            # Call ComfyUI's /settings API to mark tutorial as completed
            requests.post(
                f"{self.server_url}/settings/Comfy.TutorialCompleted",
                json=True,
                timeout=5,
            )
        except Exception:
            pass  # Best effort - server might not be running yet

    def _close_panels_and_alerts(self) -> None:
        """Close Templates sidebar panel if open."""
        try:
            # Click the X button (pi-times icon) on Templates panel
            self._page.evaluate("""
                (() => {
                    const closeIcon = document.querySelector('i.pi.pi-times');
                    if (closeIcon) closeIcon.click();
                })();
            """)
            self._page.wait_for_timeout(200)
        except Exception:
            pass

    def _fit_graph_to_view(self) -> None:
        """Fit the entire graph/workflow in the viewport.

        Uses the '.' keyboard shortcut which triggers ComfyUI's built-in
        "Fit view to selection (whole graph when nothing is selected)" feature.
        """
        try:
            # Press '.' to trigger fit view (ComfyUI keyboard shortcut)
            self._page.keyboard.press(".")
            self._page.wait_for_timeout(500)
        except Exception:
            pass  # Best effort

    def __enter__(self) -> "WorkflowScreenshot":
        self.start()
        return self

    def __exit__(self, *args) -> None:
        self.stop()

    def capture(
        self,
        workflow_path: Path,
        output_path: Optional[Path] = None,
        wait_ms: int = 2000,
    ) -> Path:
        """Capture a screenshot of a workflow.

        Args:
            workflow_path: Path to the workflow JSON file
            output_path: Path to save the PNG (default: same as workflow with .png extension)
            wait_ms: Time to wait after loading for graph to render (default: 2000ms)

        Returns:
            Path to the saved screenshot

        Raises:
            ScreenshotError: If capture fails
        """
        if self._page is None:
            raise ScreenshotError("Browser not started. Call start() or use context manager.")

        # Determine output path
        if output_path is None:
            output_path = workflow_path.with_suffix(".png")

        # Load workflow JSON
        try:
            with open(workflow_path) as f:
                workflow = json.load(f)
        except Exception as e:
            raise ScreenshotError(f"Failed to load workflow: {workflow_path}", str(e))

        self._log(f"Capturing: {workflow_path.name}")

        # Set server-side setting to prevent Templates panel from showing
        self._disable_first_run_tutorial()

        # Navigate to ComfyUI
        try:
            self._page.goto(self.server_url, wait_until="networkidle")
        except Exception as e:
            raise ScreenshotError(f"Failed to connect to ComfyUI at {self.server_url}", str(e))

        # Wait for app to initialize
        try:
            self._page.wait_for_function(
                "typeof window.app !== 'undefined' && window.app.graph !== undefined",
                timeout=30000,
            )
        except Exception as e:
            raise ScreenshotError("ComfyUI app did not initialize", str(e))

        # Load the workflow via JavaScript
        workflow_json = json.dumps(workflow)
        try:
            self._page.evaluate(f"""
                (async () => {{
                    const workflow = {workflow_json};
                    await window.app.loadGraphData(workflow);
                }})();
            """)
        except Exception as e:
            raise ScreenshotError("Failed to load workflow into ComfyUI", str(e))

        # Wait for graph to render
        self._page.wait_for_timeout(wait_ms)

        # Fit the entire graph in view
        self._fit_graph_to_view()

        # Close any open panels (Templates sidebar) and dismiss alerts
        self._close_panels_and_alerts()

        # Take screenshot with a temp file first
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            # Full viewport screenshot (1920x1080 at 2x scale)
            self._page.screenshot(path=str(tmp_path))

            # Embed workflow metadata into PNG
            self._embed_workflow(tmp_path, output_path, workflow)

        finally:
            # Clean up temp file
            if tmp_path.exists():
                tmp_path.unlink()

        self._log(f"  Saved: {output_path}")
        return output_path

    def capture_after_execution(
        self,
        workflow_path: Path,
        output_path: Optional[Path] = None,
        timeout: int = 300,
        wait_after_completion_ms: int = 3000,
    ) -> Path:
        """Capture a screenshot after executing a workflow.

        Unlike capture(), this method actually executes the workflow and waits
        for it to complete before taking a screenshot. This shows the preview
        nodes with their actual rendered outputs (images, meshes, etc.).

        Args:
            workflow_path: Path to the workflow JSON file
            output_path: Path to save the PNG (default: workflow with _executed.png suffix)
            timeout: Max seconds to wait for execution to complete (default: 300)
            wait_after_completion_ms: Time to wait after completion for previews to render (default: 3000ms)

        Returns:
            Path to the saved screenshot

        Raises:
            ScreenshotError: If capture or execution fails
        """
        if self._page is None:
            raise ScreenshotError("Browser not started. Call start() or use context manager.")

        # Determine output path - use _executed suffix to distinguish from static screenshots
        if output_path is None:
            output_path = workflow_path.with_stem(workflow_path.stem + "_executed").with_suffix(".png")

        # Load workflow JSON
        try:
            with open(workflow_path) as f:
                workflow = json.load(f)
        except Exception as e:
            raise ScreenshotError(f"Failed to load workflow: {workflow_path}", str(e))

        self._log(f"Executing and capturing: {workflow_path.name}")

        # Set server-side setting to prevent Templates panel from showing
        self._disable_first_run_tutorial()

        # Navigate to ComfyUI
        try:
            self._page.goto(self.server_url, wait_until="networkidle")
        except Exception as e:
            raise ScreenshotError(f"Failed to connect to ComfyUI at {self.server_url}", str(e))

        # Wait for app to initialize
        try:
            self._page.wait_for_function(
                "typeof window.app !== 'undefined' && window.app.graph !== undefined",
                timeout=30000,
            )
        except Exception as e:
            raise ScreenshotError("ComfyUI app did not initialize", str(e))

        # Load the workflow via JavaScript
        workflow_json = json.dumps(workflow)
        try:
            self._page.evaluate(f"""
                (async () => {{
                    const workflow = {workflow_json};
                    await window.app.loadGraphData(workflow);
                }})();
            """)
        except Exception as e:
            raise ScreenshotError("Failed to load workflow into ComfyUI", str(e))

        # Wait for graph to render before execution
        self._page.wait_for_timeout(2000)

        # Queue the workflow - just call queuePrompt() and wait
        self._log("  Queuing workflow for execution...")
        self._page.evaluate("window.app.queuePrompt()")

        # Wait for "X job completed" notification to appear (indicates execution done)
        self._log("  Waiting for execution to complete...")
        try:
            self._page.wait_for_selector('text=/\\d+ job completed/i', timeout=timeout * 1000)
        except Exception:
            pass  # Continue even if not found - might have already disappeared

        # Extra wait for previews to fully render
        self._page.wait_for_timeout(wait_after_completion_ms)
        self._log("  Execution completed")

        # Fit the entire graph in view
        self._fit_graph_to_view()

        # Close any open panels (Templates sidebar) and dismiss alerts
        self._close_panels_and_alerts()

        # Take screenshot with a temp file first
        with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
            tmp_path = Path(tmp.name)

        try:
            # Full viewport screenshot (1920x1080 at 2x scale)
            self._page.screenshot(path=str(tmp_path))

            # Embed workflow metadata into PNG
            self._embed_workflow(tmp_path, output_path, workflow)

        finally:
            # Clean up temp file
            if tmp_path.exists():
                tmp_path.unlink()

        self._log(f"  Saved: {output_path}")
        return output_path

    def _embed_workflow(
        self,
        source_path: Path,
        output_path: Path,
        workflow: dict,
    ) -> None:
        """Embed workflow JSON into PNG metadata.

        Uses the same format as ComfyUI's "Save (embed workflow)" feature,
        so the resulting PNG can be dragged back into ComfyUI.

        Args:
            source_path: Path to the source PNG
            output_path: Path to save the PNG with metadata
            workflow: Workflow dictionary to embed
        """
        img = Image.open(source_path)

        # Create PNG metadata
        pnginfo = PngImagePlugin.PngInfo()
        pnginfo.add_text("workflow", json.dumps(workflow))

        # If workflow has "prompt" format (API format), also embed that
        if "nodes" not in workflow and all(k.isdigit() for k in workflow.keys()):
            # This looks like API format (prompt)
            pnginfo.add_text("prompt", json.dumps(workflow))

        # Ensure output directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        # Save with metadata
        img.save(output_path, pnginfo=pnginfo)
        img.close()


def capture_workflows(
    workflow_paths: list[Path],
    output_dir: Optional[Path] = None,
    server_url: str = "http://127.0.0.1:8188",
    width: int = 1920,
    height: int = 1080,
    log_callback: Optional[Callable[[str], None]] = None,
) -> list[Path]:
    """Convenience function to capture multiple workflow screenshots.

    Args:
        workflow_paths: List of workflow JSON file paths
        output_dir: Custom output directory (default: same as each workflow)
        server_url: URL of running ComfyUI server
        width: Viewport width
        height: Viewport height
        log_callback: Optional logging callback

    Returns:
        List of paths to saved screenshots

    Example:
        >>> paths = capture_workflows(
        ...     [Path("workflow1.json"), Path("workflow2.json")],
        ...     server_url="http://localhost:8188",
        ... )
    """
    log = log_callback or (lambda msg: print(msg))
    results = []

    with WorkflowScreenshot(server_url, width, height, log) as ws:
        for workflow_path in workflow_paths:
            if output_dir:
                output_path = output_dir / workflow_path.with_suffix(".png").name
            else:
                output_path = None  # Same directory as workflow

            try:
                result = ws.capture(workflow_path, output_path)
                results.append(result)
            except ScreenshotError as e:
                log(f"  ERROR: {e.message}")
                if e.details:
                    log(f"  {e.details}")

    return results
