"""
tests/ui/switchback.py -- view-persistence acceptance: Find -> Compare ->
Find lands on identical figures and controls in <= 1.5 s, AND Compare ->
Find -> Compare lands on the same two institutions and the same figures.

Drives the REAL Streamlit app (one `streamlit run Menu.py` server, headless,
matching `probe.py`/`run_stress.py`'s own launch pattern: `netstat`-resolved
real PID not needed here -- this script never samples RSS -- but stdout
still goes to a FILE, never `subprocess.PIPE`/DEVNULL, matching `run_
stress.py`'s own documented reason: this app logs on every scenario
build/swap and an unread pipe fills and blocks the server once enough of
that accumulates).

TWO BATTERIES, one server session, `--runs` (default 3) repeats of each:
`one_run` (FLOW below) and `compare_roundtrip_run` (the reverse direction --
opens Compare with both slots already filled, visits Find, comes back;
its own header comment carries the full flow). Both must pass for a zero
exit code.

FLOW (one run of `one_run`):
  1. Open Find fresh (`?seed=I68947357`, Universite de Strasbourg).
  2. Expand the topic-planes panel; set "Topics shown" to "Topics led" and
     the slider to 30 (both persisted controls, `state.PERSIST`).
  3. Record: a stable hash of each of the two topic-plane figures' own
     RENDERED content, and the value of every persisted control checked
     below.
  4. Navigate to Compare via a REAL sidebar nav-link click (`page.goto`
     between two pages under a persistence claim tears down the browser's
     own WebSocket session and resets it -- the exact rule `tests/ui/
     smoke.py`'s own module docstring states and `_click_nav` embodies,
     ported here verbatim). Slot 0 auto-fills Strasbourg via Find's own
     `state.set_find_seed` hand-off; slot 1 is filled by typing CNRS's
     exact display name into the second search box (a single-hit exact
     match, `lib/search.py`'s own "a whole-field match is ALWAYS 'exact'
     priority" rule) -- this reaches the SAME `?compare=I68947357,
     I1294671590` URL a reader sharing this exact pair would see, by real
     interaction rather than a session-destroying `goto`. Waits for
     Compare's LAST chart (the
     reciprocity scatter, or its yearly-fallback-bar sibling for a pair
     below the joint floor -- not this anchor pair, but the wait covers
     both shapes).
  5. Navigate back to Find via a real nav-link click -- TIMED from the
     click to the first figure that is not behind a collapsed expander
     (`fig_breakdown_global`, row 2 of the profile section).
  6. Re-expand the topic-planes panel -- TIMED from that click to BOTH
     plane figures rendered (the figure-cache HIT path: expected "well
     under" 1.5 s, disclosed and reported explicitly even though it is
     also hard-asserted below).
  7. Record the same figure hashes and control values again; assert both
     are identical to step 3, and both timings are <= 1.5 s.

FIGURE-CONTENT HASH -- Plotly `el.data`/`el.layout`, not SVG path data
(justification): this codebase's own `tests/ui/smoke.py` already reads
`el.data`/`el.layout` live (its own DOM-facts note, "the Plotly `el.data`/
`el.layout` introspection helpers") to prove a chart "renders with data" --
a proven-safe access pattern in THIS exact build, not a fresh guess. It is
also the more STABLE choice: `el.data`/`el.layout` are exactly the JSON
Plotly.newPlot was called with (marker positions, hover text, colours,
sizes), with no rendering-pipeline noise -- SVG path data can carry
sub-pixel/attribute-ordering jitter between two otherwise-identical
`Plotly.newPlot` calls that has nothing to do with whether the underlying
FIGURE is the same. `JSON.stringify({data, layout})`, sha256'd.

PERSISTED CONTROLS CHECKED -- one of each widget TYPE this app's PERSIST
convention covers, spanning both the pre-existing set and the newer
topic-plane controls (`tree`/`basis`: selectbox; `breakdown_dim`/
`topic_mode`: segmented_control; `sort_fields`/`topic_fwci_stat`: radio;
`c1_on`/`l7_on`: checkbox; `topic_n`: slider) -- not literally every keyed
widget on the page. Excluded on purpose: expander open/closed state and
the active tab (not a persistable widget value by Streamlit's own design);
`seed_pick` (a selectbox this app's own code deliberately never persists
-- its own options list changes on every query edit, so a stale persisted
pick would be invalid); `tbl_aspirational`/`tbl_topic_overlap` (`st.
dataframe` has no `persist_state` kwarg at all on the installed Streamlit
build, confirmed by introspecting the widget signatures before writing
this file).

DOM selectors below (segmented_control's `button[aria-checked]`, the
slider's `input[type=range]` `value`/keyboard step, radio's `label[data-
selected]`) were established by LIVE probing against this exact build
before writing a single assertion here (the same discipline `tests/ui/
smoke.py`'s own header comment describes for its own checks) -- not
guessed from Streamlit's generic docs.

Usage:
    python tests/ui/switchback.py [--port 8680] [--runs 3]

Exit 0 iff every run's controls are identical, every run's figure hashes
are identical, and every run's both timings are <= 1.5 s; 1 otherwise.
Stdout is ASCII-safe (cp1252 console).
"""
from __future__ import annotations

import argparse
import hashlib
import socket
import subprocess
import sys
import time
from pathlib import Path

from playwright.sync_api import sync_playwright

STATUS_WIDGET = '[data-testid="stStatusWidget"]'

APP_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APP_DIR))

for _stream in (sys.stdout, sys.stderr):
    if getattr(_stream, "encoding", "").lower() not in ("utf-8", "utf8"):
        _stream.reconfigure(encoding="utf-8")

STRASBOURG_ID = "I68947357"
CNRS_ID = "I1294671590"
CNRS_SEARCH_TEXT = "Centre National de la Recherche Scientifique"  # exact display_name -> single-hit auto-select

ACTION_TIMEOUT_MS = 30_000
FIGURE_TIMEOUT_MS = 60_000
TARGET_S = 1.5

TOPIC_N_MIN, TOPIC_N_MAX, TOPIC_N_STEP = 10, 100, 10
TOPIC_N_TARGET = 30

PLANE_FIGS = ["fig_plane_impact", "fig_plane_frontier"]

# Compare's own figures checked by `compare_roundtrip_run` -- every one that
# renders without an EXTRA interaction first (the Impact tab needs its own
# click; skipped on purpose, the same way the topic-planes PANEL's own
# open/closed state is excluded from the persisted-controls check above --
# the active tab is one of the disclosed "cannot persist by Streamlit
# design" exceptions, so checking it here would not test a persistence
# claim at all).
COMPARE_FIGS = ["fig_shape_profile", "fig_sdg_profile", "fig_topic_overlap_plane",
               "fig_topic_overlap_bars", "fig_relationship_yearly", "fig_reciprocity"]

RESULTS: list[dict] = []
COMPARE_RESULTS: list[dict] = []


# ------------------------------------------------------------- harness -----

def _wait_for_port(port: int, timeout: float = 90.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.5)
    return False


def _start_server(port: int, log_path: Path) -> subprocess.Popen:
    log_f = open(log_path, "w", encoding="utf-8", errors="replace")
    return subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "Menu.py",
         "--server.headless", "true", "--server.port", str(port),
         "--browser.gatherUsageStats", "false"],
        cwd=str(APP_DIR), stdout=log_f, stderr=subprocess.STDOUT)


def _stop_server(server: subprocess.Popen) -> None:
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=10)


# ------------------------------------------------------------ DOM: nav -----

def _nav_link(page, label: str):
    """Resolves (never clicks) the sidebar nav-link locator for `label` --
    kept separate from the click so a TIMED transition can start its clock
    exactly at `.click()`, not at the locator resolution/visibility wait."""
    page.wait_for_selector('[data-testid="stSidebarNav"]', state="attached", timeout=ACTION_TIMEOUT_MS)
    link = page.locator('[data-testid="stSidebarNav"] a').filter(has_text=label).first
    link.wait_for(state="visible", timeout=ACTION_TIMEOUT_MS)
    return link


def _wait_idle(page, timeout_ms: int = 30_000) -> None:
    """Polls for Streamlit's own running/status widget to clear -- the same
    signal `tests/stress/run_stress.py`'s own `wait_idle` uses -- so a TIMED
    transition's clock never starts (or a control-setting step never hands
    off) while a PRIOR rerun this script itself triggered is still in
    flight server-side."""
    deadline = time.time() + timeout_ms / 1000
    page.wait_for_timeout(100)
    while time.time() < deadline:
        if page.locator(STATUS_WIDGET).count() == 0:
            return
        page.wait_for_timeout(150)


def _click_nav(page, label: str, settle_ms: int = 1500) -> None:
    """Untimed real nav-link click (Find -> Compare): `page.goto` between
    two pages tears down the WebSocket session under a persistence claim
    -- see module docstring and `tests/ui/smoke.py`'s own `_click_nav`,
    ported verbatim."""
    _nav_link(page, label).click(timeout=ACTION_TIMEOUT_MS)
    page.wait_for_timeout(settle_ms)


# ------------------------------------------------------- DOM: controls -----

def _selectbox_value(page, key: str) -> str:
    return page.locator(f".st-key-{key} input").first.input_value()


def _seg_value(page, key: str) -> str:
    return page.locator(f".st-key-{key} button[aria-checked='true']").first.inner_text().strip()


def _set_seg(page, key: str, text: str) -> None:
    page.locator(f".st-key-{key} button[data-variant='segmented_control']") \
        .filter(has_text=text).first.click(timeout=ACTION_TIMEOUT_MS)


def _radio_value(page, key: str) -> str:
    return page.locator(f".st-key-{key} label[data-selected='true']").first.inner_text().strip()


def _slider_value(page, key: str) -> str:
    return page.locator(f".st-key-{key} input[type='range']").first.get_attribute("value")


def _set_slider(page, key: str, target: int, step: int) -> None:
    """Focuses the (accessibly hidden, but keyboard-tabbable) `<input
    type=range>` and steps it with arrow keys -- live-verified before this
    file was written that this build's slider genuinely moves by `step`
    per key press (not a drag-only widget)."""
    inp = page.locator(f".st-key-{key} input[type='range']").first
    inp.click(force=True, timeout=ACTION_TIMEOUT_MS)
    current = int(inp.get_attribute("value"))
    presses = int(round((target - current) / step))
    key_name = "ArrowRight" if presses > 0 else "ArrowLeft"
    for _ in range(abs(presses)):
        inp.press(key_name)
        page.wait_for_timeout(80)


def _checkbox_value(page, key: str) -> bool:
    return page.locator(f".st-key-{key} input[type='checkbox']").first.is_checked()


# One of each widget TYPE this app's PERSIST convention covers -- see
# module docstring for the excluded categories and why.
CONTROLS: list[tuple[str, str]] = [
    ("tree", "select"), ("basis", "select"),
    ("breakdown_dim", "seg"), ("sort_fields", "radio"),
    ("c1_on", "check"), ("l7_on", "check"),
    ("topic_mode", "seg"), ("topic_n", "slider"), ("topic_fwci_stat", "radio"),
]
_READERS = {"select": _selectbox_value, "seg": _seg_value, "radio": _radio_value,
           "slider": _slider_value, "check": _checkbox_value}


def _read_controls(page) -> dict:
    return {key: _READERS[kind](page, key) for key, kind in CONTROLS}


# -------------------------------------------------------- DOM: figures -----

def _figure_hash(page, key: str) -> str | None:
    """sha256 of `JSON.stringify({data: el.data, layout: el.layout})` for
    `.st-key-{key} .js-plotly-plot` -- see module docstring for why this,
    not SVG path data."""
    js = page.evaluate(
        "(sel) => { const el = document.querySelector(sel); "
        "if (!el || !el.data) return null; "
        "return JSON.stringify({data: el.data, layout: el.layout}); }",
        f".st-key-{key} .js-plotly-plot")
    if js is None:
        return None
    return hashlib.sha256(js.encode("utf-8")).hexdigest()


def _read_plane_hashes(page) -> dict:
    return {k: _figure_hash(page, k) for k in PLANE_FIGS}


def _read_compare_figure_hashes(page) -> dict:
    return {k: _figure_hash(page, k) for k in COMPARE_FIGS}


def _slot_labels(page) -> dict:
    """The two Compare slot selectboxes' own DISPLAYED text (an institution
    name, or the "Empty slot" placeholder) -- `compare_slot_{i}` is a plain
    `st.selectbox`, the SAME `.st-key-{key} input`'s `.input_value()`
    pattern `_selectbox_value` already reads for `tree`/`basis`."""
    return {"slot0": _selectbox_value(page, "compare_slot_0"),
            "slot1": _selectbox_value(page, "compare_slot_1")}


# ------------------------------------------------------------- one run -----

def one_run(page, base: str, run_no: int) -> dict:
    log: list[str] = []

    def note(msg: str) -> None:
        log.append(msg)
        print(f"  [run {run_no}] {msg}")

    # 1. open Find fresh
    page.goto(f"{base}/Find?seed={STRASBOURG_ID}", wait_until="domcontentloaded")
    page.wait_for_selector(".st-key-profile", state="attached", timeout=ACTION_TIMEOUT_MS)
    page.wait_for_timeout(2500)
    note("Find opened (seed=Strasbourg)")

    # 2. expand the topics panel; set selector + slider
    page.locator(".st-key-panel_topic_planes summary").click(timeout=ACTION_TIMEOUT_MS)
    page.wait_for_timeout(1200)
    _set_seg(page, "topic_mode", "Topics led")
    page.wait_for_timeout(800)
    _set_slider(page, "topic_n", TOPIC_N_TARGET, TOPIC_N_STEP)
    page.wait_for_timeout(1500)
    page.wait_for_selector(".st-key-fig_plane_frontier .js-plotly-plot", timeout=FIGURE_TIMEOUT_MS)
    page.wait_for_timeout(500)
    note(f"topic planes set: mode={_seg_value(page, 'topic_mode')!r} n={_slider_value(page, 'topic_n')!r}")

    # 3. record BEFORE state
    before_hashes = _read_plane_hashes(page)
    before_controls = _read_controls(page)
    missing = [k for k, v in before_hashes.items() if v is None]
    assert not missing, f"Find plane(s) did not render before leaving: {missing}"

    # 4. Find -> Compare (untimed; real nav click). Slot 0 auto-fills
    # Strasbourg via Find's own find_seed hand-off (live-verified). Slot 1:
    # Compare's own selectbox does NOT auto-select on a single hit the way
    # Find's `_seed_pick` does (live-verified: typing + Enter alone leaves
    # it "Empty slot") -- type the query to populate the option list, THEN
    # open the combobox (react-aria, `role=combobox` `aria-label="Slot 2"`,
    # NOT a `[data-baseweb=select]` on this build -- live-verified; the
    # SAME `get_by_role("combobox", ...)` idiom `tests/stress/run_stress.
    # py`'s own `resolve_picker_if_present` already uses) and click the
    # matching option.
    _click_nav(page, "Compare", settle_ms=1500)
    page.wait_for_selector(".st-key-compare_slot_0", state="attached", timeout=ACTION_TIMEOUT_MS)
    page.wait_for_timeout(1200)
    slot1_query = page.locator(".st-key-compare_slot_query_1 input").first
    slot1_query.fill(CNRS_SEARCH_TEXT)
    slot1_query.press("Enter")
    page.wait_for_timeout(1200)
    slot1_combo = page.get_by_role("combobox", name="Slot 2")
    slot1_combo.first.click(timeout=ACTION_TIMEOUT_MS)
    page.wait_for_timeout(300)
    slot1_option = page.get_by_role("option").filter(has_text="Centre National")
    slot1_option.first.click(timeout=ACTION_TIMEOUT_MS)
    page.wait_for_timeout(2500)
    page.wait_for_selector(
        ".st-key-fig_reciprocity .js-plotly-plot, "
        ".st-key-fig_relationship_yearly .js-plotly-plot, "
        ".st-key-fig_relationship_yearly_fallback .js-plotly-plot",
        timeout=FIGURE_TIMEOUT_MS)
    page.wait_for_timeout(800)
    _wait_idle(page)
    note(f"Compare opened (url={page.url})")
    exceptions_on_compare = page.locator('[data-testid="stException"]').count()

    # 5. Compare -> Find, TIMED to the first non-collapsed figure. `_wait_
    # idle` just above guarantees the click lands on a genuinely settled
    # app (no rerun this script itself triggered still in flight) so the
    # clock below times ONLY the transition this step is measuring.
    find_link = _nav_link(page, "Find")
    t0 = time.perf_counter()
    find_link.click(timeout=ACTION_TIMEOUT_MS)
    page.wait_for_selector(".st-key-fig_breakdown_global .js-plotly-plot", timeout=FIGURE_TIMEOUT_MS)
    t_page_switch = time.perf_counter() - t0
    page.wait_for_timeout(300)
    _wait_idle(page)
    note(f"back on Find: page_switch_s={t_page_switch:.3f}")

    # 6. re-expand the topics panel, TIMED to BOTH planes rendered
    summary = page.locator(".st-key-panel_topic_planes summary").first
    t1 = time.perf_counter()
    summary.click(timeout=ACTION_TIMEOUT_MS)
    page.wait_for_selector(".st-key-fig_plane_impact .js-plotly-plot", timeout=FIGURE_TIMEOUT_MS)
    page.wait_for_selector(".st-key-fig_plane_frontier .js-plotly-plot", timeout=FIGURE_TIMEOUT_MS)
    t_planes_after_expand = time.perf_counter() - t1
    page.wait_for_timeout(500)
    note(f"planes re-rendered: planes_after_expand_s={t_planes_after_expand:.3f}")

    # 7. record AFTER state
    after_hashes = _read_plane_hashes(page)
    after_controls = _read_controls(page)
    exceptions_on_find = page.locator('[data-testid="stException"]').count()

    controls_identical = before_controls == after_controls
    figures_identical = before_hashes == after_hashes

    if not controls_identical:
        for k in before_controls:
            if before_controls[k] != after_controls.get(k):
                note(f"CONTROL DRIFT {k}: before={before_controls[k]!r} after={after_controls.get(k)!r}")
    if not figures_identical:
        for k in before_hashes:
            if before_hashes[k] != after_hashes.get(k):
                note(f"FIGURE HASH DRIFT {k}: before={before_hashes[k]} after={after_hashes.get(k)}")

    return {
        "run": run_no,
        "page_switch_s": round(t_page_switch, 3),
        "planes_after_expand_s": round(t_planes_after_expand, 3),
        "controls_identical": controls_identical,
        "figures_identical": figures_identical,
        "exceptions": exceptions_on_compare + exceptions_on_find,
        "page_switch_ok": t_page_switch <= TARGET_S,
        "planes_after_expand_ok": t_planes_after_expand <= TARGET_S,
        "before_controls": before_controls,
        "after_controls": after_controls,
        "log": log,
    }


# ------------------------------------------------- Compare round trip run --
# View persistence covers the Compare slot pickers too, not only the
# topic-plane controls above: opens Compare directly (both slots filled),
# visits Find, comes back -- the SAME real-nav-click discipline as
# `one_run`, in the opposite direction. Proves
# `lib/selection.py:render_slots`' own fix (`**state.PERSIST` added to the
# `compare_slot_{i}` selectbox -- see that module's own STREAMLIT TOUCHPOINT
# note for why the fix has to live on the widget itself, not merely in the
# one-shot hydration block's plain session_state write).

def compare_roundtrip_run(page, base: str, run_no: int) -> dict:
    log: list[str] = []

    def note(msg: str) -> None:
        log.append(msg)
        print(f"  [compare-rt {run_no}] {msg}")

    # 1. open Compare fresh, both slots filled via the URL
    page.goto(f"{base}/Compare?compare={STRASBOURG_ID},{CNRS_ID}", wait_until="domcontentloaded")
    page.wait_for_selector(".st-key-compare_slot_0", state="attached", timeout=ACTION_TIMEOUT_MS)
    page.wait_for_timeout(2000)
    page.wait_for_selector(
        ".st-key-fig_reciprocity .js-plotly-plot, "
        ".st-key-fig_relationship_yearly .js-plotly-plot, "
        ".st-key-fig_relationship_yearly_fallback .js-plotly-plot",
        timeout=FIGURE_TIMEOUT_MS)
    page.wait_for_timeout(800)
    _wait_idle(page)

    before_labels = _slot_labels(page)
    before_hashes = _read_compare_figure_hashes(page)
    missing = [k for k, v in before_hashes.items() if v is None]
    assert not missing, f"Compare figure(s) did not render before leaving: {missing}"
    note(f"Compare opened: slot0={before_labels['slot0']!r} slot1={before_labels['slot1']!r}")

    # 2. Compare -> Find (untimed; real nav click -- never page.goto under a
    # persistence claim, see module docstring)
    _click_nav(page, "Find", settle_ms=1500)
    page.wait_for_selector(".st-key-seed_query", state="attached", timeout=ACTION_TIMEOUT_MS)
    page.wait_for_timeout(500)
    _wait_idle(page)
    exceptions_on_find = page.locator('[data-testid="stException"]').count()
    note("visited Find")

    # 3. Find -> Compare, TIMED to Compare's last chart
    compare_link = _nav_link(page, "Compare")
    t0 = time.perf_counter()
    compare_link.click(timeout=ACTION_TIMEOUT_MS)
    page.wait_for_selector(
        ".st-key-fig_reciprocity .js-plotly-plot, "
        ".st-key-fig_relationship_yearly .js-plotly-plot, "
        ".st-key-fig_relationship_yearly_fallback .js-plotly-plot",
        timeout=FIGURE_TIMEOUT_MS)
    seconds = time.perf_counter() - t0
    page.wait_for_timeout(500)
    note(f"back on Compare: seconds={seconds:.3f}")

    # 4. record AFTER state
    after_labels = _slot_labels(page)
    after_hashes = _read_compare_figure_hashes(page)
    exceptions_on_compare = page.locator('[data-testid="stException"]').count()

    slots_identical = before_labels == after_labels
    figures_identical = before_hashes == after_hashes
    if not slots_identical:
        note(f"SLOT DRIFT: before={before_labels} after={after_labels}")
    if not figures_identical:
        for k in before_hashes:
            if before_hashes[k] != after_hashes.get(k):
                note(f"FIGURE HASH DRIFT {k}: before={before_hashes[k]} after={after_hashes.get(k)}")

    return {
        "run": run_no,
        "seconds": round(seconds, 3),
        "slots_identical": slots_identical,
        "figures_identical": figures_identical,
        "exceptions": exceptions_on_find + exceptions_on_compare,
        "before_labels": before_labels,
        "after_labels": after_labels,
        "log": log,
    }


# -------------------------------------------------------------------- main -

def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8680)
    parser.add_argument("--runs", type=int, default=3)
    args = parser.parse_args()

    base = f"http://127.0.0.1:{args.port}"
    log_path = APP_DIR / "tests" / "ui" / "switchback_server.log"
    print(f"[switchback] starting server on port {args.port} ... log: {log_path}")
    server = _start_server(args.port, log_path)
    try:
        if not _wait_for_port(args.port, timeout=90):
            print("FAIL: server did not open its port within 90s")
            return 1

        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(viewport={"width": 1280, "height": 1000})
            page = context.new_page()
            page.set_default_timeout(ACTION_TIMEOUT_MS)

            for i in range(1, args.runs + 1):
                print(f"\n=== switchback run {i}/{args.runs} ===")
                try:
                    RESULTS.append(one_run(page, base, i))
                except Exception as exc:  # noqa: BLE001 -- one run's crash must not skip the rest
                    print(f"  [run {i}] RAISED {type(exc).__name__}: {exc}")
                    RESULTS.append({
                        "run": i, "page_switch_s": None, "planes_after_expand_s": None,
                        "controls_identical": False, "figures_identical": False,
                        "exceptions": -1, "page_switch_ok": False, "planes_after_expand_ok": False,
                        "before_controls": {}, "after_controls": {}, "log": [f"RAISED: {exc}"],
                    })

            for i in range(1, args.runs + 1):
                print(f"\n=== switchback compare-roundtrip run {i}/{args.runs} ===")
                try:
                    COMPARE_RESULTS.append(compare_roundtrip_run(page, base, i))
                except Exception as exc:  # noqa: BLE001 -- one run's crash must not skip the rest
                    print(f"  [compare-rt {i}] RAISED {type(exc).__name__}: {exc}")
                    COMPARE_RESULTS.append({
                        "run": i, "seconds": None, "slots_identical": False,
                        "figures_identical": False, "exceptions": -1,
                        "before_labels": {}, "after_labels": {}, "log": [f"RAISED: {exc}"],
                    })

            page.close()
            context.close()
            browser.close()
    finally:
        _stop_server(server)

    print("\n=== switchback summary ===")
    header = f"{'run':>3} | {'page_switch_s':>13} | {'planes_after_expand_s':>22} | {'controls':>8} | {'figures':>7} | {'exc':>3}"
    print(header)
    print("-" * len(header))
    for r in RESULTS:
        ps = f"{r['page_switch_s']:.3f}" if r["page_switch_s"] is not None else "ERR"
        pa = f"{r['planes_after_expand_s']:.3f}" if r["planes_after_expand_s"] is not None else "ERR"
        print(f"{r['run']:>3} | {ps:>13} | {pa:>22} | {str(r['controls_identical']):>8} | "
             f"{str(r['figures_identical']):>7} | {r['exceptions']:>3}")

    all_ok = all(
        r["controls_identical"] and r["figures_identical"] and r["exceptions"] == 0
        and r["page_switch_ok"] and r["planes_after_expand_ok"]
        for r in RESULTS
    )
    if not all_ok:
        print("\nFAILED runs / reasons:")
        for r in RESULTS:
            if not (r["controls_identical"] and r["figures_identical"] and r["exceptions"] == 0
                   and r["page_switch_ok"] and r["planes_after_expand_ok"]):
                reasons = []
                if not r["controls_identical"]:
                    reasons.append("controls drifted")
                if not r["figures_identical"]:
                    reasons.append("figure hashes drifted")
                if r["exceptions"]:
                    reasons.append(f"{r['exceptions']} Streamlit exception(s)")
                if not r["page_switch_ok"]:
                    reasons.append(f"page_switch_s {r['page_switch_s']} > {TARGET_S}")
                if not r["planes_after_expand_ok"]:
                    reasons.append(f"planes_after_expand_s {r['planes_after_expand_s']} > {TARGET_S}")
                print(f"  run {r['run']}: {', '.join(reasons)}")

    print("\n=== switchback compare-roundtrip summary ===")
    header2 = f"{'run':>3} | {'seconds':>8} | {'slots':>7} | {'figures':>7} | {'exc':>3}"
    print(header2)
    print("-" * len(header2))
    for r in COMPARE_RESULTS:
        secs = f"{r['seconds']:.3f}" if r["seconds"] is not None else "ERR"
        print(f"{r['run']:>3} | {secs:>8} | {str(r['slots_identical']):>7} | "
             f"{str(r['figures_identical']):>7} | {r['exceptions']:>3}")

    compare_ok = all(
        r["slots_identical"] and r["figures_identical"] and r["exceptions"] == 0
        for r in COMPARE_RESULTS
    )
    if not compare_ok:
        print("\nFAILED compare-roundtrip runs / reasons:")
        for r in COMPARE_RESULTS:
            if not (r["slots_identical"] and r["figures_identical"] and r["exceptions"] == 0):
                reasons = []
                if not r["slots_identical"]:
                    reasons.append(f"slots drifted (before={r['before_labels']} after={r['after_labels']})")
                if not r["figures_identical"]:
                    reasons.append("figure hashes drifted")
                if r["exceptions"]:
                    reasons.append(f"{r['exceptions']} Streamlit exception(s)")
                print(f"  run {r['run']}: {', '.join(reasons)}")

    if not (all_ok and compare_ok):
        print("\nRESULT: FAIL")
        return 1

    print("\nRESULT: PASS -- every run of both batteries: identical controls/slots, "
         "identical figures, no exceptions, both Find-side timings <= 1.5s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
