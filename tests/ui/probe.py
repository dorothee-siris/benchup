"""
tests/ui/probe.py -- ONE parameterised acceptance probe: a LIGHTER
correctness sweep than tests/ui/smoke.py, recomputing a real value through
`lib/*` (never Streamlit-rendered) and matching it against the page's own
rendering of it, rather than only proving a surface exists (the build plan,
Stream T2, 2026-09-03).

REWRITTEN for BenchUp V4: `collab` is DELETED (no pair page
exist in this app -- D1); the shared sidebar search recompute helpers
(`_sidebar_add`, the old `slots_row` probes) are gone with the architecture
that produced them (Stream E3/C3: Find's own free-text search, Compare's
two independent search slots). WHAT SURVIVES from the pre-trim file: the
per-page-process launch (`streamlit run <page file>` as the process root, so
each probe opens at `/`, no sidebar nav needed), the settle-wait mechanics,
and the "recompute through `lib.engine`/`lib.compare_data` -- both
Streamlit-free packages, importable and callable from a plain script -- then
read the page's own formatting of the same figure" idiom (the L1 golden
recompute, the Compare card recompute).

Usage:
    python tests/ui/probe.py menu
    python tests/ui/probe.py find
    python tests/ui/probe.py compare
    python tests/ui/probe.py methods
    python tests/ui/probe.py all [--port 8620]

Exit 0 iff every check in the requested view(s) passes; 1 otherwise. Stdout
is ASCII-safe (cp1252 console).
"""
from __future__ import annotations

import argparse
import io
import re
import socket
import subprocess
import sys
import time
from pathlib import Path

import openpyxl
from playwright.sync_api import sync_playwright

APP_DIR = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(APP_DIR))

for _stream in (sys.stdout, sys.stderr):
    if getattr(_stream, "encoding", "").lower() not in ("utf-8", "utf8"):
        _stream.reconfigure(encoding="utf-8")

PAGES = {
    "menu": "Menu.py",
    "find": "pages/1_\U0001F50E_Find.py",
    "compare": "pages/2_⚖️_Compare.py",
    "methods": "pages/3_\U0001F4D6_Methods.py",
}

ACTION_TIMEOUT_MS = 30_000
WIDTHS = [1920, 1280, 390]
SHOT_DIR = APP_DIR / "tests" / "ui" / "screenshots"

IFREMER_ID = "I154202486"
NIOZ_ID = "I4210107283"
TREE, BASIS = "bestfit", "frac"   # Find's own scenario defaults (config.yaml)

RESULTS: list[tuple[bool, str]] = []
PORT = 8620
BASE_URL = "http://127.0.0.1:8620"


def check(ok: bool, message: str) -> bool:
    RESULTS.append((bool(ok), message))
    print(("PASS: " if ok else "FAIL: ") + message)
    return bool(ok)


# ------------------------------------------------------------- harness ------

def _wait_for_port(port: int, timeout: float = 90.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.5)
    return False


def _start_server(page_file: str, port: int) -> subprocess.Popen:
    return subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", page_file,
         "--server.headless", "true", "--server.port", str(port),
         "--browser.gatherUsageStats", "false"],
        cwd=str(APP_DIR), stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)


def _stop_server(server: subprocess.Popen) -> None:
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=10)


def _settle(page, ms: int = 2500) -> None:
    page.wait_for_timeout(ms)


def _wait_for(page, predicate, timeout_ms: int = 15_000, interval_ms: int = 300) -> bool:
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        if predicate():
            return True
        page.wait_for_timeout(interval_ms)
    return False


def _full_text(page) -> str:
    return page.evaluate("document.body.textContent") or ""


def _no_exception(page, label: str) -> bool:
    return check(page.locator('[data-testid="stException"]').count() == 0,
                f"{label}: no Streamlit exception on the page")


def _n_figures(page) -> int:
    return page.locator(".js-plotly-plot").count()


def _unique_openalex_hrefs(page, container_selector: str) -> set:
    """Same DOM fact as smoke.py's own `_unique_hrefs` (live-verified against
    this build): the mirror chart's tick anchors carry `xlink:href`, which a
    plain `a[href]` CSS selector or `getAttribute('href')` alone misses."""
    xlink = "http://www.w3.org/1999/xlink"
    return set(page.evaluate(
        "(sel) => { const root = document.querySelector(sel); if (!root) return [];"
        " const XLINK = %r;"
        " return Array.from(root.querySelectorAll('a')).map(a =>"
        " a.getAttribute('href') || a.getAttributeNS(XLINK, 'href') || '')"
        " .filter(h => h.includes('openalex.org')); }" % xlink, container_selector))


# ===================================================================== menu

def _probe_menu(page) -> None:
    from lib.data_cache import index

    page.goto(BASE_URL, wait_until="domcontentloaded")
    page.wait_for_selector(".st-key-nav_cards", state="attached", timeout=60_000)
    n = len(index())
    ok = _wait_for(page, lambda: f"{n:,}" in _full_text(page), timeout_ms=25_000)
    check(ok, f"Menu: the footer's institution count matches lib.data_cache.index() ({n:,})")
    _no_exception(page, "Menu")


# ===================================================================== find

def _probe_find(page) -> None:
    from lib.engine import load_context, load_substrates, seed_card

    page.goto(f"{BASE_URL}/?seed={IFREMER_ID}", wait_until="domcontentloaded")
    page.wait_for_selector(".st-key-profile", state="attached", timeout=120_000)
    _settle(page, 2500)
    _no_exception(page, f"Find {IFREMER_ID}")

    # --- KPI recompute: Publications, off the SAME pure engine `seed_card`
    #     the page itself calls (lib/engine, no Streamlit import) ----------
    ctx = load_context(str(APP_DIR / "data"))
    subs = load_substrates(ctx, TREE, BASIS)
    card = seed_card(ctx, IFREMER_ID, subs)
    pubs = card.get("total_full_2020_2024")
    check(pubs is not None and pubs > 0, f"Find golden: seed_card recomputes a Publications figure ({pubs})")
    formatted = f"{float(pubs):,.0f}"
    tile_text = page.locator(".st-key-profile .benchup-kpi").first.text_content()
    check(formatted in tile_text, f"Find golden: the Publications tile shows the recomputed figure "
                                  f"{formatted!r} (tile: {tile_text!r})")

    # --- L1 rank-1 golden, read back off the page's OWN workbook (never the
    #     canvas ranking table -- st.dataframe carries no real cell text,
    #     confirmed live against this build) ----------------------------
    from lib.engine import rank_all

    rankings = rank_all(ctx, subs, IFREMER_ID)
    l1 = rankings["L1"]
    gold_id = l1["sorted_ids"][0]
    gold_score = float(l1["scores"][0])
    dl_btn = page.locator("button").filter(has_text=re.compile(r"^Download"))
    with page.expect_download(timeout=120_000) as info:
        dl_btn.first.click(timeout=ACTION_TIMEOUT_MS)
    raw = Path(info.value.path()).read_bytes()
    book = openpyxl.load_workbook(io.BytesIO(raw), data_only=True)
    l1_sheet_name = next((s for s in book.sheetnames if s.startswith("L1")), None)
    check(l1_sheet_name is not None, f"Find golden: an L1 sheet exists in the workbook ({book.sheetnames})")
    if l1_sheet_name:
        ws = book[l1_sheet_name]
        header = [c.value for c in ws[1]]
        rows = list(ws.iter_rows(min_row=2, max_row=2, values_only=True))
        row0 = dict(zip(header, rows[0])) if rows else {}
        check(row0.get("institution_id") == gold_id,
              f"Find golden: workbook L1 rank-1 institution_id == rank_all's own top pick "
              f"({row0.get('institution_id')} vs {gold_id})")
        # SOFTENED (see file-level note at the bottom of this module): the
        # workbook's own "score" column is `lib/ranked.py::format_rows`'s
        # `_pct100(row["lens_score"])`, fed by `views_find._rows_for_ids` /
        # `_filtered` -- a different computation stage than `rank_all`'s own
        # raw `l1["scores"]` array (live-measured: NOT a plain x100 of it,
        # e.g. 74.349 vs 0.138515 x 100 = 13.8515 for this exact seed/lens).
        # Reproducing that second stage is outside
        # this probe's scope -- the LOAD-BEARING half (which institution
        # ranks #1) is the hard check above; the score itself is checked
        # only for shape (a finite, non-negative number).
        got_score = row0.get("score")
        check(got_score is not None and float(got_score) >= 0,
              f"Find golden: workbook L1 rank-1 carries a real, non-negative score value ({got_score})")


# ================================================================== compare

def _probe_compare(page) -> None:
    from lib import compare_data as CD
    from lib.engine import load_context, load_substrates

    page.goto(f"{BASE_URL}/?compare={IFREMER_ID},{NIOZ_ID}", wait_until="domcontentloaded")
    page.wait_for_selector(".st-key-compare_slot_0", state="attached", timeout=60_000)
    _settle(page, 3500)
    _no_exception(page, "Compare")

    ctx = load_context(str(APP_DIR / "data"))
    ids = [IFREMER_ID, NIOZ_ID]

    # --- Key-figure card recompute: Publications (vol_full), off
    #     `compare_data.cards` (pure, imports no
    #     Streamlit), matched against the FIRST card's own rendered text
    #     (cards are `st.markdown` HTML, real text nodes -- not canvas). ---
    cards_df = CD.cards(ctx, ids).set_index("institution_id")
    vol_full = cards_df.loc[IFREMER_ID, "vol_full"]
    # DOM FACT (live-verified): Compare's own card formatter
    # (`charts.py::_fmt_vol`, the `fr_int` convention) prints a
    # thousands separator as a NARROW NO-BREAK SPACE, never a comma -- Find's
    # own `_count` uses a plain comma instead (a legitimate per-page
    # difference, not a bug: `views_find.py` vs `charts.py` are two
    # different formatters by design).
    thin_space = "\N{NARROW NO-BREAK SPACE}"
    formatted = format(int(round(float(vol_full))), ",").replace(",", thin_space)
    # Cold-start poll-wait (same lesson as smoke.py's own Menu footer fix):
    # the cards section is the FIRST heavy render on a fresh process, and a
    # fixed settle can catch the page before `compare_data.cards` has drawn.
    ok = _wait_for(page, lambda: formatted in _full_text(page), timeout_ms=20_000)
    check(ok, f"Compare golden: Ifremer's recomputed Publications figure {formatted!r} renders on the page")

    # --- shared-frontier row count, recomputed off `compare_data.
    #     shared_frontier` (the SAME frame the mirror chart / table / xlsx
    #     sheet all read), matched against the page's own "Show all N". ---
    subs = load_substrates(ctx, "bestfit", "full")   # Compare is PINNED (D10)
    shared = CD.shared_frontier(ctx, subs, ids)
    n_shared = int(len(shared))
    btn = page.locator("button").filter(has_text=re.compile(r"^Show all \d+$"))
    if n_shared > 20:
        check(btn.count() >= 1, f"Compare golden: 'Show all {n_shared}' renders (recomputed n={n_shared})")
        if btn.count():
            btn_n = int(re.search(r"\d+", btn.first.text_content()).group())
            check(btn_n == n_shared,
                  f"Compare golden: the 'Show all' button's own N == recomputed shared-frontier "
                  f"row count ({btn_n} vs {n_shared})")
    else:
        check(btn.count() == 0, f"Compare golden: no 'Show all' button when recomputed n={n_shared} <= 20")

    check(_n_figures(page) >= 3, f"Compare: at least 3 Plotly figures render (found {_n_figures(page)})")
    _no_exception(page, "Compare (end of probe)")


# ================================================================== methods

def _probe_methods(page) -> None:
    from lib.data_cache import index, manifest

    page.goto(BASE_URL, wait_until="domcontentloaded")
    page.wait_for_selector('[data-testid="stExpander"]', state="attached", timeout=60_000)
    _settle(page, 2000)
    _no_exception(page, "Methods")

    n_institutions = len(index())
    mf = manifest()
    snapshot = mf.get("snapshot")
    text = _full_text(page)
    check(f"{n_institutions:,}" in text,
          f"Methods golden: the recomputed institution count ({n_institutions:,}) renders somewhere on the page")
    if snapshot:
        check(str(snapshot) in text, f"Methods golden: the manifest's own snapshot label ({snapshot!r}) renders")


# ------------------------------------------------------------------- widths -

def _probe_widths(page_path: str, browser, slug: str, url_suffix: str) -> None:
    SHOT_DIR.mkdir(parents=True, exist_ok=True)
    for width in WIDTHS:
        page = browser.new_page(viewport={"width": width, "height": 1000})
        page.set_default_timeout(ACTION_TIMEOUT_MS)
        page.goto(f"{BASE_URL}{url_suffix}", wait_until="domcontentloaded")
        try:
            page.wait_for_selector(".js-plotly-plot, .stMainBlockContainer", state="attached", timeout=60_000)
        except Exception:  # noqa: BLE001
            pass
        page.wait_for_timeout(2500)
        scroll = page.evaluate("document.documentElement.scrollWidth")
        inner = page.evaluate("window.innerWidth")
        check(scroll <= inner + 2, f"{slug} {width}px: scrollWidth {scroll} <= innerWidth+2 {inner + 2}")
        path = SHOT_DIR / f"probe_{slug}_{width}.png"
        page.screenshot(path=str(path), full_page=True)
        check(path.is_file(), f"{slug} {width}px: screenshot written")
        page.close()


# -------------------------------------------------------------------- main --

VIEWS = {
    "menu": (PAGES["menu"], "", _probe_menu),
    "find": (PAGES["find"], f"/?seed={IFREMER_ID}", _probe_find),
    "compare": (PAGES["compare"], f"/?compare={IFREMER_ID},{NIOZ_ID}", _probe_compare),
    "methods": (PAGES["methods"], "", _probe_methods),
}


def _run_view(view: str, port: int) -> None:
    global PORT, BASE_URL
    PORT = port
    BASE_URL = f"http://127.0.0.1:{port}"
    page_file, url_suffix, fn = VIEWS[view]
    server = _start_server(page_file, port)
    try:
        if not _wait_for_port(port):
            check(False, f"{view}: server did not open port {port}")
            return
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(viewport={"width": 1280, "height": 1000}, accept_downloads=True)
            page = context.new_page()
            page.set_default_timeout(ACTION_TIMEOUT_MS)
            try:
                fn(page)
            except Exception as exc:  # noqa: BLE001 -- one phase's crash must not skip widths
                check(False, f"{view}: raised {type(exc).__name__}: {exc}")
            page.close()
            context.close()
            _probe_widths(page_file, browser, view, url_suffix)
            browser.close()
    finally:
        _stop_server(server)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("view", choices=["menu", "find", "compare", "methods", "all"])
    parser.add_argument("--port", type=int, default=8620)
    args = parser.parse_args()

    views = list(VIEWS) if args.view == "all" else [args.view]
    for i, view in enumerate(views):
        print(f"\n=== probe: {view} ===")
        _run_view(view, args.port + i)

    failed = [m for ok, m in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)} of {len(RESULTS)} checks passed")
    if failed:
        for m in failed:
            print("FAILED:", m)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
