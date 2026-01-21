"""HTML report generator for test results.

This module generates an index.html file from test results that can be:
- Served locally via `ct show` for development preview
- Published to gh-pages for public visibility

The same HTML is used in both contexts, ensuring parity between local and deployed views.
"""

import html
import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional


def generate_html_report(output_dir: Path, repo_name: Optional[str] = None) -> Path:
    """Generate index.html from results.json and screenshots.

    This is the single source of truth - used for both:
    - Local preview via `ct show`
    - gh-pages publishing in CI

    Args:
        output_dir: Directory containing results.json, screenshots/, logs/
        repo_name: Optional repository name for the header

    Returns:
        Path to the generated index.html file
    """
    results_file = output_dir / "results.json"
    screenshots_dir = output_dir / "screenshots"
    logs_dir = output_dir / "logs"

    if not results_file.exists():
        raise FileNotFoundError(f"No results.json found in {output_dir}")

    results = json.loads(results_file.read_text())

    # Discover available screenshots and logs
    screenshots = {f.stem.replace("_executed", ""): f.name
                   for f in screenshots_dir.glob("*.png")} if screenshots_dir.exists() else {}
    log_files = {f.stem: f.name
                 for f in logs_dir.glob("*.log")} if logs_dir.exists() else {}

    # Read log contents
    log_contents = {}
    for name, filename in log_files.items():
        try:
            content = (logs_dir / filename).read_text(errors='replace')
            # Limit log size to prevent huge HTML files
            if len(content) > 50000:
                content = content[:50000] + "\n... (truncated)"
            log_contents[name] = content
        except Exception:
            log_contents[name] = "(Could not read log file)"

    # Infer repo name from directory if not provided
    if repo_name is None:
        # Try to get from parent directory name (e.g., ComfyUI-GeometryPack)
        repo_name = output_dir.parent.name
        if repo_name in (".", ".comfy-test"):
            repo_name = output_dir.parent.parent.name

    html_content = _render_report(results, screenshots, log_contents, repo_name)

    output_file = output_dir / "index.html"
    output_file.write_text(html_content)
    return output_file


def _render_report(
    results: Dict[str, Any],
    screenshots: Dict[str, str],
    log_contents: Dict[str, str],
    repo_name: str,
) -> str:
    """Render the HTML report from results data.

    Args:
        results: Parsed results.json data
        screenshots: Dict mapping workflow name to screenshot filename
        log_contents: Dict mapping workflow name to log content
        repo_name: Repository name for the header

    Returns:
        Complete HTML document as string
    """
    summary = results.get("summary", {})
    total = summary.get("total", 0)
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    workflows = results.get("workflows", [])
    timestamp = results.get("timestamp", "")
    platform = results.get("platform", "unknown")

    # Parse timestamp for display
    try:
        dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        timestamp_display = dt.strftime("%Y-%m-%d %H:%M UTC")
    except (ValueError, AttributeError):
        timestamp_display = timestamp

    # Calculate pass rate
    pass_rate = (passed / total * 100) if total > 0 else 0

    # Separate failed and passed workflows
    failed_workflows = [w for w in workflows if w.get("status") == "fail"]
    all_workflows = workflows

    # Build workflow cards HTML
    failed_section = _render_failed_section(failed_workflows, log_contents)
    workflow_cards, workflow_data_js = _render_workflow_cards(all_workflows, screenshots, log_contents)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{repo_name} - Test Results</title>
    <style>
        * {{ margin: 0; padding: 0; box-sizing: border-box; }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: #1a1a2e;
            color: #eee;
            min-height: 100vh;
            line-height: 1.5;
        }}

        header {{
            background: #16213e;
            padding: 1.5rem 2rem;
            border-bottom: 1px solid #0f3460;
        }}

        h1 {{
            font-size: 1.5rem;
            margin-bottom: 0.25rem;
        }}

        h1 a {{
            color: #fff;
            text-decoration: none;
        }}

        h1 a:hover {{ color: #4da6ff; }}

        .meta {{
            color: #888;
            font-size: 0.9rem;
        }}

        .container {{
            max-width: 1400px;
            margin: 0 auto;
            padding: 1.5rem;
        }}

        /* Summary Section */
        .summary {{
            background: #16213e;
            border-radius: 8px;
            padding: 1.5rem;
            margin-bottom: 1.5rem;
        }}

        .progress-bar {{
            background: #0f3460;
            border-radius: 4px;
            height: 24px;
            overflow: hidden;
            margin-bottom: 1rem;
        }}

        .progress-fill {{
            background: linear-gradient(90deg, #00c853, #69f0ae);
            height: 100%;
            transition: width 0.3s ease;
        }}

        .progress-fill.has-failures {{
            background: linear-gradient(90deg, #00c853 0%, #00c853 {pass_rate}%, #ff5252 {pass_rate}%, #ff5252 100%);
            width: 100% !important;
        }}

        .stats {{
            display: flex;
            gap: 1rem;
            flex-wrap: wrap;
            align-items: center;
        }}

        .stat-badge {{
            padding: 0.5rem 1rem;
            border-radius: 4px;
            font-weight: 600;
            font-size: 0.9rem;
        }}

        .stat-pass {{
            background: rgba(0, 200, 83, 0.2);
            color: #69f0ae;
        }}

        .stat-fail {{
            background: rgba(255, 82, 82, 0.2);
            color: #ff8a80;
        }}

        .stat-total {{
            color: #888;
            font-size: 1rem;
        }}

        /* Failed Section */
        .failed-section {{
            background: rgba(255, 82, 82, 0.1);
            border: 1px solid rgba(255, 82, 82, 0.3);
            border-radius: 8px;
            padding: 1rem;
            margin-bottom: 1.5rem;
        }}

        .failed-section h2 {{
            color: #ff8a80;
            font-size: 1rem;
            margin-bottom: 1rem;
            display: flex;
            align-items: center;
            gap: 0.5rem;
        }}

        .failed-item {{
            background: #16213e;
            border-radius: 6px;
            padding: 1rem;
            margin-bottom: 0.5rem;
        }}

        .failed-item:last-child {{
            margin-bottom: 0;
        }}

        .failed-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.5rem;
        }}

        .failed-name {{
            font-weight: 600;
            color: #ff8a80;
        }}

        .failed-duration {{
            color: #888;
            font-size: 0.85rem;
        }}

        .failed-error {{
            background: #0f3460;
            padding: 0.75rem;
            border-radius: 4px;
            font-family: monospace;
            font-size: 0.85rem;
            color: #ffa;
            margin-bottom: 0.5rem;
        }}

        .log-link {{
            color: #4da6ff;
            text-decoration: none;
            font-size: 0.85rem;
        }}

        .log-link:hover {{
            text-decoration: underline;
        }}

        /* Workflow Grid */
        .section-title {{
            font-size: 1rem;
            color: #888;
            margin-bottom: 1rem;
            text-transform: uppercase;
            letter-spacing: 0.05em;
        }}

        .workflow-grid {{
            display: grid;
            grid-template-columns: repeat(auto-fill, minmax(280px, 1fr));
            gap: 1rem;
        }}

        .workflow-card {{
            background: #16213e;
            border-radius: 8px;
            overflow: hidden;
            transition: transform 0.2s, box-shadow 0.2s;
        }}

        .workflow-card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        }}

        .workflow-card.clickable {{
            cursor: pointer;
        }}

        .workflow-card.failed {{
            border: 2px solid #ff5252;
            box-shadow: 0 0 8px rgba(255, 82, 82, 0.3);
        }}

        .workflow-screenshot {{
            width: 100%;
            aspect-ratio: 16/10;
            object-fit: cover;
            background: #0f3460;
            display: block;
        }}

        .workflow-screenshot.placeholder {{
            display: flex;
            align-items: center;
            justify-content: center;
            color: #444;
            font-size: 0.85rem;
        }}

        .workflow-info {{
            padding: 0.75rem 1rem;
            border-top: 1px solid #0f3460;
        }}

        .workflow-header {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            margin-bottom: 0.25rem;
        }}

        .workflow-name {{
            font-weight: 500;
            font-size: 0.9rem;
            white-space: nowrap;
            overflow: hidden;
            text-overflow: ellipsis;
            max-width: 60%;
        }}

        .workflow-badge {{
            padding: 0.2rem 0.5rem;
            border-radius: 3px;
            font-size: 0.75rem;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .workflow-badge.pass {{
            background: rgba(0, 200, 83, 0.2);
            color: #69f0ae;
        }}

        .workflow-badge.fail {{
            background: rgba(255, 82, 82, 0.2);
            color: #ff8a80;
        }}

        .workflow-meta {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            font-size: 0.8rem;
            color: #666;
        }}

        /* Lightbox */
        .lightbox {{
            display: none;
            position: fixed;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            background: rgba(0,0,0,0.95);
            z-index: 1000;
            justify-content: center;
            align-items: flex-start;
            padding: 2rem;
            overflow-y: auto;
        }}

        .lightbox.active {{
            display: flex;
        }}

        .lightbox-content {{
            display: flex;
            flex-direction: column;
            max-width: 1200px;
            width: 100%;
            margin: auto;
        }}

        .lightbox-content img {{
            max-width: 100%;
            max-height: 60vh;
            object-fit: contain;
            border-radius: 4px;
            align-self: center;
        }}

        .lightbox-close {{
            position: fixed;
            top: 1rem;
            right: 1.5rem;
            font-size: 2rem;
            color: #fff;
            cursor: pointer;
            opacity: 0.7;
            background: none;
            border: none;
            z-index: 1001;
        }}

        .lightbox-close:hover {{
            opacity: 1;
        }}

        .lightbox-info {{
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 1rem;
            background: #16213e;
            border-radius: 4px;
            margin-top: 1rem;
        }}

        .lightbox-title {{
            font-size: 1.1rem;
            font-weight: 600;
            color: #fff;
        }}

        .lightbox-meta {{
            display: flex;
            gap: 1rem;
            align-items: center;
        }}

        .lightbox-badge {{
            padding: 0.25rem 0.75rem;
            border-radius: 4px;
            font-size: 0.85rem;
            font-weight: 600;
            text-transform: uppercase;
        }}

        .lightbox-badge.pass {{
            background: rgba(0, 200, 83, 0.2);
            color: #69f0ae;
        }}

        .lightbox-badge.fail {{
            background: rgba(255, 82, 82, 0.2);
            color: #ff8a80;
        }}

        .lightbox-duration {{
            color: #888;
            font-size: 0.9rem;
        }}

        .lightbox-log {{
            background: #0f3460;
            border-radius: 4px;
            padding: 1rem;
            margin-top: 1rem;
            max-height: 300px;
            overflow-y: auto;
            font-family: 'Monaco', 'Menlo', 'Ubuntu Mono', monospace;
            font-size: 0.8rem;
            line-height: 1.4;
            white-space: pre-wrap;
            word-break: break-all;
            color: #ccc;
        }}

        .lightbox-log::-webkit-scrollbar {{
            width: 8px;
        }}

        .lightbox-log::-webkit-scrollbar-track {{
            background: #16213e;
            border-radius: 4px;
        }}

        .lightbox-log::-webkit-scrollbar-thumb {{
            background: #4da6ff;
            border-radius: 4px;
        }}

        /* Footer */
        footer {{
            text-align: center;
            padding: 2rem;
            color: #666;
            font-size: 0.85rem;
        }}

        footer a {{
            color: #4da6ff;
            text-decoration: none;
        }}

        footer a:hover {{
            text-decoration: underline;
        }}

        /* Responsive */
        @media (max-width: 600px) {{
            .workflow-grid {{
                grid-template-columns: 1fr;
            }}

            .stats {{
                flex-direction: column;
                align-items: flex-start;
            }}
        }}
    </style>
</head>
<body>
    <header>
        <h1><a href="https://github.com/PozzettiAndrea/{repo_name}">{repo_name}</a></h1>
        <p class="meta">Test Results | {timestamp_display} | Platform: {platform}</p>
    </header>

    <div class="container">
        <div class="summary">
            <div class="progress-bar">
                <div class="progress-fill{' has-failures' if failed > 0 else ''}" style="width: {pass_rate}%"></div>
            </div>
            <div class="stats">
                <span class="stat-badge stat-pass">{passed} PASSED</span>
                {f'<span class="stat-badge stat-fail">{failed} FAILED</span>' if failed > 0 else ''}
                <span class="stat-total">{passed}/{total} tests ({pass_rate:.1f}%)</span>
            </div>
        </div>

        {failed_section}

        <h2 class="section-title">All Workflows</h2>
        <div class="workflow-grid">
            {workflow_cards}
        </div>
    </div>

    <div class="lightbox" id="lightbox">
        <button class="lightbox-close" onclick="closeLightbox()">&times;</button>
        <div class="lightbox-content">
            <img id="lightbox-img" src="" alt="">
            <div class="lightbox-info">
                <span class="lightbox-title" id="lightbox-title"></span>
                <div class="lightbox-meta">
                    <span class="lightbox-badge" id="lightbox-badge"></span>
                    <span class="lightbox-duration" id="lightbox-duration"></span>
                </div>
            </div>
            <pre class="lightbox-log" id="lightbox-log"></pre>
        </div>
    </div>

    <footer>
        Generated by <a href="https://github.com/PozzettiAndrea/comfy-test">comfy-test</a>
    </footer>

    <script>
        // Store workflow data for hash-based linking
        const workflowData = {workflow_data_js};

        function openLightbox(src, title, status, duration, logContent) {{
            document.getElementById('lightbox-img').src = src;
            document.getElementById('lightbox-title').textContent = title;

            const badge = document.getElementById('lightbox-badge');
            badge.textContent = status;
            badge.className = 'lightbox-badge ' + status;

            document.getElementById('lightbox-duration').textContent = duration + 's';
            document.getElementById('lightbox-log').textContent = logContent || '(No log available)';
            document.getElementById('lightbox').classList.add('active');

            // Update URL hash for shareable link
            history.replaceState(null, '', '#' + encodeURIComponent(title));
        }}

        function closeLightbox() {{
            document.getElementById('lightbox').classList.remove('active');
            // Clear hash
            history.replaceState(null, '', window.location.pathname);
        }}

        document.getElementById('lightbox').onclick = (e) => {{
            if (e.target.id === 'lightbox') closeLightbox();
        }};

        document.onkeydown = (e) => {{
            if (e.key === 'Escape') closeLightbox();
        }};

        // Handle hash on page load and hash change
        function openFromHash() {{
            const hash = decodeURIComponent(window.location.hash.slice(1));
            if (hash && workflowData[hash]) {{
                const w = workflowData[hash];
                openLightbox(w.src, w.title, w.status, w.duration, w.log);
            }}
        }}

        window.addEventListener('hashchange', openFromHash);
        window.addEventListener('load', openFromHash);
    </script>
</body>
</html>'''


def _render_failed_section(failed_workflows: List[Dict], log_contents: Dict[str, str]) -> str:
    """Render the failed tests section."""
    if not failed_workflows:
        return ""

    items = []
    for w in failed_workflows:
        name = w.get("name", "unknown")
        duration = w.get("duration_seconds", 0)
        error = w.get("error", "Unknown error")

        items.append(f'''
            <div class="failed-item">
                <div class="failed-header">
                    <span class="failed-name">{name}</span>
                    <span class="failed-duration">{duration:.2f}s</span>
                </div>
                <div class="failed-error">{html.escape(error)}</div>
            </div>
        ''')

    return f'''
        <div class="failed-section">
            <h2>Failed Tests</h2>
            {''.join(items)}
        </div>
    '''


def _render_workflow_cards(
    workflows: List[Dict],
    screenshots: Dict[str, str],
    log_contents: Dict[str, str],
) -> tuple:
    """Render workflow cards for the grid.

    Returns:
        Tuple of (cards_html, workflow_data_js)
    """
    cards = []
    workflow_data = {}

    for w in workflows:
        name = w.get("name", "unknown")
        status = w.get("status", "unknown")
        duration = w.get("duration_seconds", 0)
        screenshot_file = screenshots.get(name, "")
        log_content = log_contents.get(name, "")

        # Escape log content for JavaScript string
        log_escaped = html.escape(log_content).replace('\\', '\\\\').replace("'", "\\'").replace('\n', '\\n').replace('\r', '\\r')

        # Store data for hash-based linking
        src = f'screenshots/{screenshot_file}' if screenshot_file else ''
        workflow_data[name] = {
            'src': src,
            'title': name,
            'status': status,
            'duration': f'{duration:.2f}',
            'log': log_content
        }

        # Add failed class for red border
        failed_class = "failed" if status == "fail" else ""

        # Screenshot or placeholder
        if screenshot_file:
            screenshot_html = f'''
                <img class="workflow-screenshot" src="screenshots/{screenshot_file}"
                     alt="{name}" loading="lazy">
            '''
            onclick = f'''onclick="openLightbox('{src}', '{name}', '{status}', '{duration:.2f}', '{log_escaped}')"'''
            clickable = "clickable"
        else:
            screenshot_html = '<div class="workflow-screenshot placeholder">No screenshot</div>'
            # Still allow clicking to see log even without screenshot
            onclick = f'''onclick="openLightbox('', '{name}', '{status}', '{duration:.2f}', '{log_escaped}')"'''
            clickable = "clickable"

        cards.append(f'''
            <div class="workflow-card {clickable} {failed_class}" {onclick}>
                {screenshot_html}
                <div class="workflow-info">
                    <div class="workflow-header">
                        <span class="workflow-name" title="{name}">{name}</span>
                        <span class="workflow-badge {status}">{status}</span>
                    </div>
                    <div class="workflow-meta">
                        <span>{duration:.2f}s</span>
                    </div>
                </div>
            </div>
        ''')

    # Convert workflow data to JSON for JavaScript
    workflow_data_js = json.dumps(workflow_data)

    return '\n'.join(cards), workflow_data_js
