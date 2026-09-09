"""
tests/ui/hover_shots.py -- hover render check: screenshots
the ACTUAL rendered hover box of three charts against the live app, so the
manager reads pixels rather than a customdata string.

Drives a REAL Streamlit server (the same subprocess-launch/poll-wait
lifecycle `tests/ui/smoke.py` uses; stdout to a FILE, never PIPE/DEVNULL,
matching `tests/ui/switchback.py`'s own documented reason -- this app logs on
every scenario build and an unread pipe fills and blocks the server once
enough of that accumulates over a run this long) at a FIXED 1280 px viewport
(the width this stream's brief names). Three charts, each reached the same
way `tests/ui/smoke.py`/`switchback.py` already reach it live:
  1. Find's plane A ("Volume, impact and frontier" panel, `fig_plane_impact`)
     -- seeded via `?seed=I68947357` (Universite de Strasbourg).
  2. Compare's balance bars (Topic overlap, `fig_topic_overlap_bars`) --
     `?compare=I68947357,I1294671590` (Strasbourg x CNRS).
  3. Compare's reciprocity scatter (`fig_reciprocity`) -- same pair, same
     page load.
Each hover is triggered by a real `page.mouse.move` onto the first rendered
mark's own centre pixel (a genuine mousemove Plotly's own hover engine
reacts to, not a synthetic DOM event) -- never `.hover()` alone, which can
no-op on an SVG `path` Playwright considers non-actionable under a covering
draglayer. The FULL PAGE screenshot is saved (not a hoverlayer-only crop):
Plotly's hover label can render several hundred px tall on an 8-line hover,
and a fixed crop box measured on one chart is not safe on the next.

Usage:
    python tests/ui/hover_shots.py [--port 8630] [--out-dir <dir>]

Exit 0 iff every chart produced a visible hover label AND neither page
scrolls sideways at 1280 px; 1 otherwise. Prints one PASS/FAIL line per
check plus the saved PNG paths.
"""
from __future__ import annotations

import argparse
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

for _stream in (sys.stdout, sys.stderr):
    if getattr(_stream, "encoding", "").lower() not in ("utf-8", "utf8"):
        _stream.reconfigure(encoding="utf-8")

APP_DIR = Path(__file__).resolve().parents[2]     # tests/ui/hover_shots.py -> app/
V4_DIR = APP_DIR.parent                            # app/ -> V4/
DEFAULT_OUT_DIR = V4_DIR / "progress"

ACTION_TIMEOUT_MS = 30_000
VIEWPORT_WIDTH = 1280
VIEWPORT_HEIGHT = 1400   # tall enough that the profile header + first panel need no scroll

STRASBOURG_ID = "I68947357"
CNRS_ID = "I1294671590"

RESULTS: list[tuple[bool, str]] = []


def check(ok: bool, message: str) -> bool:
    RESULTS.append((bool(ok), message))
    print(("PASS: " if ok else "FAIL: ") + message)
    return bool(ok)


# ------------------------------------------------------------- server -------
def _wait_for_port(port: int, timeout: float = 90.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.5)
    return False


def _port_already_up(port: int) -> bool:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        return sock.connect_ex(("127.0.0.1", port)) == 0


def _start_server(app_dir: Path, port: int, log_path: Path) -> subprocess.Popen:
    log_file = open(log_path, "w", encoding="utf-8")
    return subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "Menu.py",
         "--server.headless", "true", "--server.port", str(port),
         "--browser.gatherUsageStats", "false"],
        cwd=str(app_dir), stdout=log_file, stderr=subprocess.STDOUT)


def _stop_server(server: subprocess.Popen) -> None:
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=10)


# --------------------------------------------------------- DOM helpers ------
def _settle(page, ms: int = 2000) -> None:
    page.wait_for_timeout(ms)


def _no_sideways_scroll(page, label: str) -> bool:
    scroll = page.evaluate("document.documentElement.scrollWidth")
    inner = page.evaluate("window.innerWidth")
    return check(scroll <= inner + 2, f"{label}: scrollWidth {scroll} <= innerWidth+2 {inner + 2}")


MAX_HOVER_CANDIDATES = 15   # how many marks this tries before giving up


def _hover_first_mark_and_shoot(page, chart_selector: str, out_path: Path, label: str) -> bool:
    """Waits for `chart_selector`'s Plotly SVG, then moves the REAL mouse
    onto successive rendered marks (`.points path`, the shape both
    `go.Scatter(mode="markers")` and `go.Bar` marks render as) in DOCUMENT
    order until Plotly's own `.hoverlayer` gains a child (the hover label),
    then saves a FULL PAGE screenshot. Trying more than one candidate (never
    just "the first") matters on a multi-trace overlay bar chart like
    `balance_bars`: its own phantom GUTTER trace ships `hoverinfo="skip"` by
    design (`lib/charts_topics.py`'s own docstring) and interleaves into the
    same `.points path` list, and a genuinely zero-value bar segment (an
    A-only segment of 0 on a topic B holds alone) renders with no real
    hoverable area either -- neither is a bug, both are simply not "the
    first mark a reader could actually point at", so this tries the next
    one instead of failing the render check on an unlucky index."""
    page.wait_for_selector(f"{chart_selector} .js-plotly-plot", state="attached", timeout=60_000)
    _settle(page, 1500)
    points = page.locator(f"{chart_selector} .points path")
    n = points.count()
    if n == 0:
        return check(False, f"{label}: no rendered mark found under {chart_selector!r}")
    for i in range(min(n, MAX_HOVER_CANDIDATES)):
        point = points.nth(i)
        # A tall bar chart (e.g. balance_bars' ~30+ rows) puts an early mark
        # WAY below an 1280px-wide fold -- `bounding_box()` still returns
        # page-absolute coordinates for an off-screen element, and a
        # mouse.move there lands nowhere real. `scroll_into_view_if_needed`
        # first, THEN read the (now on-screen) box.
        point.scroll_into_view_if_needed(timeout=ACTION_TIMEOUT_MS)
        _settle(page, 300)
        box = point.bounding_box()
        if box is None:
            continue
        cx, cy = box["x"] + box["width"] / 2, box["y"] + box["height"] / 2
        page.mouse.move(cx - 2, cy - 2)
        page.mouse.move(cx, cy)   # a second move: Plotly's hover distance check re-fires on delta
        try:
            page.wait_for_function(
                f"document.querySelector('{chart_selector} .hoverlayer')"
                "?.childElementCount > 0",
                timeout=1500,
            )
        except Exception:
            continue
        check(True, f"{label}: the hover label appears (.hoverlayer gains a child, mark #{i})")
        _settle(page, 300)
        out_path.parent.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(out_path), full_page=False)
        print(f"SAVED: {out_path}")
        return True
    return check(False, f"{label}: no hover label appeared on the first {min(n, MAX_HOVER_CANDIDATES)} marks")


# ------------------------------------------------------------------ main ---
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--port", type=int, default=8630)
    ap.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR)
    args = ap.parse_args()

    base_url = f"http://127.0.0.1:{args.port}"
    server = None
    reused = _port_already_up(args.port)
    if not reused:
        log_path = args.out_dir / "hover_shots_server.log"
        args.out_dir.mkdir(parents=True, exist_ok=True)
        server = _start_server(APP_DIR, args.port, log_path)
        if not _wait_for_port(args.port):
            print(f"FAIL: server never opened port {args.port} (see {log_path})")
            return 1
    try:
        with sync_playwright() as pw:
            browser = pw.chromium.launch()
            page = browser.new_page(viewport={"width": VIEWPORT_WIDTH, "height": VIEWPORT_HEIGHT})
            page.set_default_timeout(ACTION_TIMEOUT_MS)

            # --- 1. Find's plane A (Strasbourg) ------------------------------
            page.goto(f"{base_url}/Find?seed={STRASBOURG_ID}", wait_until="domcontentloaded")
            page.wait_for_selector(".st-key-profile", state="attached", timeout=60_000)
            _settle(page, 1500)
            page.locator(".st-key-panel_topic_planes summary").first.click(timeout=ACTION_TIMEOUT_MS)
            _settle(page, 1500)
            _hover_first_mark_and_shoot(
                page, ".st-key-fig_plane_impact", args.out_dir / "hover_plane_a_1280.png",
                "Find plane A")
            _no_sideways_scroll(page, "Find (plane A open)")

            # --- 2/3. Compare's balance bars + reciprocity (Strasbourg x CNRS)
            page.goto(f"{base_url}/Compare?compare={STRASBOURG_ID},{CNRS_ID}",
                     wait_until="domcontentloaded")
            page.wait_for_selector(".st-key-compare_slot_0", state="attached", timeout=60_000)
            _settle(page, 2000)
            _hover_first_mark_and_shoot(
                page, ".st-key-fig_topic_overlap_bars", args.out_dir / "hover_balance_bars_1280.png",
                "Compare balance bars")
            _hover_first_mark_and_shoot(
                page, ".st-key-fig_reciprocity", args.out_dir / "hover_reciprocity_1280.png",
                "Compare reciprocity scatter")
            _no_sideways_scroll(page, "Compare (both charts hovered)")

            browser.close()
    finally:
        if server is not None:
            _stop_server(server)

    n_pass = sum(1 for ok, _ in RESULTS if ok)
    print(f"{n_pass}/{len(RESULTS)} checks passed")
    return 0 if n_pass == len(RESULTS) else 1


if __name__ == "__main__":
    sys.exit(main())
