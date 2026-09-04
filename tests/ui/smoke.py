"""
tests/ui/smoke.py -- Playwright smoke test against the LIVE Streamlit server.

REWRITTEN for BenchUp V4 (2026-09-03) against the
trimmed app: Menu (3 cards, no sidebar search) -> Find (free-text
search -> one profile, sidebar taxonomy/basis selectboxes, 8 KPI tiles, one
end-of-page workbook) -> Compare (two independent search slots, PINNED to
best-fit/full, six sections in order, one end-of-page workbook, a share
box) -> Methods ("How it is built", 15 expanders + a note download). Every
pair page / shortlist / pooled-scatter / depth-radio /
per-section-download check from the earlier harness is DELETED, not
ported: those surfaces do not exist in this app any more. The ERC profile panel on Find is IN scope
and checked below (`check_find`'s ERC block).

WHAT SURVIVES FROM THE PRE-TRIM HARNESS (mechanics only, re-verified live
against this build): the subprocess launch/poll-wait server lifecycle (three
recorded cold-start false failures were fixed by polling instead of a fixed
sleep -- kept here verbatim in spirit), the settle/wait_for polling helpers,
the keyed-widget `.st-key-<key>` selector convention, the Plotly `el.data`/
`el.layout` introspection helpers, and the "never `page.goto` between two
pages when a persistence claim is under test" rule (find_seed only survives
a real in-app nav-link click, `[data-testid="stSidebarNav"] a`; a `goto`
tears down the browser's own WebSocket session, which resets it).

DOM FACTS this file's own checks depend on, established by live probing
against this exact build before writing a single assertion below (kept as
comments at each call site too):
  * URLs: Streamlit derives clean slugs from the emoji-prefixed page files --
    `/Find`, `/Compare`, `/Methods` (confirmed live, not assumed).
  * `st.dataframe`'s glide-data-grid canvas DOES carry a real, hidden
    accessibility mirror: `[role="grid"]` with `aria-rowcount`/
    `aria-colcount`, `[role="columnheader"]`/`[role="gridcell"]` -- but only
    for the columns currently scrolled into the canvas viewport (a
    horizontal scroll via `scrollLeft` or a synthetic wheel event over the
    canvas did not bring the three link columns into that mirror in a live
    trial). `aria-colcount` itself is NOT virtualized, so the topic-overlap
    table's link-column check below reads `aria-colcount` (== 18, the full
    column list including the 3 link columns) plus a static source-grep for
    exactly 3 `LinkColumn(` calls, rather than reading rendered header text
    -- see `check_compare` and this file's own SOFTENED list at the bottom.
  * `st.tabs` renders `[data-testid="stTab"]` (not `[role="tab"]` on this
    Streamlit build).
  * A single search hit auto-selects (no `seed_pick` selectbox appears);
    "Ifremer" is single-hit on this index.

Usage:
    python tests/ui/smoke.py [--port 8611] [--sections menu,find,compare,methods,widths]

Exit 0 iff every check passes, 1 otherwise. Prints one PASS/FAIL line per
check plus a final "N/N checks passed" line. Stdout is ASCII-safe (cp1252
console -- every stream is reconfigured to utf-8 below, the same fix the
pre-trim file carried).
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

for _stream in (sys.stdout, sys.stderr):
    if getattr(_stream, "encoding", "").lower() not in ("utf-8", "utf8"):
        _stream.reconfigure(encoding="utf-8")

APP_DIR = Path(__file__).resolve().parents[2]  # tests/ui/smoke.py -> app/
WIDTHS = [1920, 1280, 390]
ACTION_TIMEOUT_MS = 30_000
SEP = "\N{MIDDLE DOT}"

# --------------------------------------------------------- reference ids ----
IFREMER_ID = "I154202486"
NIOZ_ID = "I4210107283"
STRASBOURG_ID = "I68947357"
CNRS_ID = "I1294671590"
ETH_ID = "I35440088"

# ------------------------------------------------------------- copy pins ----
# Hardcoded literals (never re-imported from lib/copy.py -- the same
# non-vacuity discipline the pre-trim file used): a copy.py edit that
# silently drifts these strings should FAIL this file, not update itself.
NAV_CARD_LABELS = ["Find peers", "Compare", "How it is built"]
FIND_KPI_LABELS = ["Publications", "SDG-tagged share", "Frontier top-quartile share",
                   "PP10_WD", "International co-publications", "Industrial co-publications",
                   "Star papers", "Topics led"]
TREE_LABELS = {
    "bestfit": "Repaired taxonomy (best fit, default)",
    "conservative": "Repaired taxonomy (conservative)",
    "original": "OpenAlex taxonomy as published",
}
BASIS_LABELS = {"frac": "Fractional counting", "full": "Full counting"}
COMPARE_SECTION_HEADERS = ["Key figures", "Thematic shape", "SDG profile", "Topic overlap",
                           "The relationship"]
COMPARE_TILE_LABELS = ["Joint publications", "Joint star papers", "Momentum"]
COMPARE_TAB_LABELS = ["Profile", "Impact"]
PROMPT_NEED_TWO = "Pick two institutions above to compare them."
SLOT_EMPTY_LABEL = "Empty slot"
FIND_XLSX_SHEET_COUNT = 15   # Profile + Overview + 10 ALL_LENSES sheets + Aspirational + leaders sheet + Topics
COMPARE_XLSX_SHEETS = ["Cards", "Subfields", "SDG", "Topic overlap",
                       "Relationship yearly", "Reciprocity"]
METHODS_SECTION_TITLES = [
    "What the tool is", "Data and windows", "Counting bases, and the Compare pin",
    "The subject taxonomy", "Two baselines, kept apart", "Frontier scores",
    "World leaders", "Star papers", "Topic planes", "Topic overlap",
    "The relationship", "Reading momentum", "Matching", "Scale guard", "Limits",
]
DATA_CAPTION_RE = re.compile(
    r"[\d,]+\s+institutions\s+" + re.escape(SEP) + r"\s+data from\s+[A-Za-z]+\s+\d{1,2},\s+\d{4}")

RESULTS: list[tuple[bool, str]] = []
FINDINGS: list[str] = []
SOFTENED: list[str] = []
PORT = 8611
BASE_URL = "http://127.0.0.1:8611"


def check(ok: bool, message: str) -> bool:
    RESULTS.append((bool(ok), message))
    print(("PASS: " if ok else "FAIL: ") + message)
    return bool(ok)


def finding(message: str) -> None:
    """A real, reproduced app behaviour outside this harness's fence --
    printed distinctly and collected
    for the run's own summary, on top of a normal `check()` line."""
    FINDINGS.append(message)
    print("FINDING: " + message)


def soften(message: str) -> None:
    SOFTENED.append(message)
    print("SOFTENED: " + message)


def fail_section(name: str, exc: Exception) -> None:
    check(False, f"{name}: raised {type(exc).__name__}: {exc}")


# ------------------------------------------------------------- server -------

def _wait_for_port(port: int, timeout: float = 90.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.5)
    return False


def _start_server(app_dir: Path, port: int) -> subprocess.Popen:
    # DEVNULL, not PIPE: an unread pipe buffer fills and blocks the server
    # mid-probe once enough reruns have logged to it (pre-trim lesson kept).
    return subprocess.Popen(
        [sys.executable, "-m", "streamlit", "run", "Menu.py",
         "--server.headless", "true", "--server.port", str(port),
         "--browser.gatherUsageStats", "false"],
        cwd=str(app_dir), stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)


def _stop_server(server: subprocess.Popen) -> None:
    server.terminate()
    try:
        server.wait(timeout=10)
    except subprocess.TimeoutExpired:
        server.kill()
        server.wait(timeout=10)


# --------------------------------------------------------- DOM helpers ------

def _settle(page, ms: int = 2500) -> None:
    page.wait_for_timeout(ms)


def _wait_for(page, predicate, timeout_ms: int = 15_000, interval_ms: int = 300) -> bool:
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        if predicate():
            return True
        page.wait_for_timeout(interval_ms)
    return False


def _full_page_text(page) -> str:
    return page.evaluate("document.body.textContent") or ""


def _no_exception(page, label: str) -> bool:
    return check(page.locator('[data-testid="stException"]').count() == 0,
                f"{label}: no Streamlit exception on the page")


def _open_select(page, key: str) -> None:
    loc = page.locator(f".st-key-{key} [data-baseweb='select']")
    if loc.count() == 0:
        loc = page.locator(f".st-key-{key}")
    loc.first.click(timeout=ACTION_TIMEOUT_MS)
    page.wait_for_selector('[role="option"]', timeout=ACTION_TIMEOUT_MS)


def _pick_option(page, text: str) -> None:
    page.locator('[role="option"]').filter(has_text=text).first.click(timeout=ACTION_TIMEOUT_MS)


def _select_options_text(page, key: str) -> list[str]:
    _open_select(page, key)
    opts = [t.strip() for t in page.locator('[role="option"]').all_text_contents() if t.strip()]
    page.keyboard.press("Escape")
    page.wait_for_timeout(300)
    return opts


def _selectbox_value(page, key: str) -> str:
    return page.locator(f".st-key-{key} input").first.input_value()


def _click_nav(page, label: str) -> None:
    """Real in-app sidebar nav-link click -- the ONLY way this file changes
    page when a persistence claim (find_seed -> Compare slot 1) is under
    test. `page.goto` tears down the browser's own WebSocket session."""
    page.wait_for_selector('[data-testid="stSidebarNav"]', state="attached", timeout=ACTION_TIMEOUT_MS)
    link = page.locator('[data-testid="stSidebarNav"] a').filter(has_text=label).first
    link.wait_for(state="visible", timeout=ACTION_TIMEOUT_MS)
    link.click(timeout=ACTION_TIMEOUT_MS)
    _settle(page, 2500)


def _unique_hrefs(page, container_selector: str, substr: str) -> set:
    """DOM FACT (live-verified): the mirror chart's y-tick anchors are real
    SVG `<a>` elements, but Plotly sets their link as `xlink:href` (the
    XLink-namespaced attribute), not a plain `href` -- a CSS `a[href]`
    selector (matches by unprefixed local name only) finds ZERO of them, and
    even `getAttribute('href')` alone returns null; `getAttributeNS` against
    the XLink namespace is required. Verified against this exact build: a
    plain-`href` HTML `<a>` elsewhere on the page (the relationship
    section's own OpenAlex link) DOES match `a[href*=...]`, so a naive
    global search silently proves the wrong thing without this fallback."""
    xlink = "http://www.w3.org/1999/xlink"
    return set(page.evaluate(
        "(sel) => { const root = document.querySelector(sel); if (!root) return [];"
        " const XLINK = %r;"
        " return Array.from(root.querySelectorAll('a')).map(a =>"
        " a.getAttribute('href') || a.getAttributeNS(XLINK, 'href') || '')"
        " .filter(h => h.includes(%r)); }" % (xlink, substr), container_selector))


def _scroll_width_ok(page) -> tuple[int, int]:
    scroll = page.evaluate("document.documentElement.scrollWidth")
    inner = page.evaluate("window.innerWidth")
    return scroll, inner


# ------------------------------------------------------------- sections -----

def check_menu(page) -> None:
    page.goto(BASE_URL, wait_until="domcontentloaded")
    page.wait_for_selector('.st-key-nav_cards', state="attached", timeout=ACTION_TIMEOUT_MS)
    # Cold-start poll-wait (kept from the pre-trim harness's own lesson,
    # three recorded false failures fixed this way): the footer's own
    # caption reads `index()`/`manifest()`, which is genuinely slow on a
    # cold process -- the card links render well before it, so a fixed
    # settle here can catch the page mid "Running index()." spinner.
    _wait_for(page, lambda: DATA_CAPTION_RE.search(_full_page_text(page)) is not None, timeout_ms=25_000)
    _no_exception(page, "Menu")
    check("BenchUp" in _full_page_text(page), "Menu: the title 'BenchUp' renders")

    for word, label in zip(("find", "compare", "methods"), NAV_CARD_LABELS):
        card = page.locator(f".st-key-nav_card_{word}")
        check(card.count() == 1, f"Menu: the {label!r} card container renders")
        check(label in card.text_content(), f"Menu: the {label!r} card carries its own label")
        check(card.locator("a").count() >= 1, f"Menu: the {label!r} card carries a live page link")

    footer = _full_page_text(page)
    m = DATA_CAPTION_RE.search(footer)
    check(m is not None, f"Menu: the footer states '<N> institutions {SEP} data from <date>' ({footer[-200:]!r})")
    if m:
        n_str = re.search(r"[\d,]+", m.group()).group().replace(",", "")
        check(int(n_str) > 1000, f"Menu: the institution count in the footer is plausible ({n_str})")
    check("Candidates for review, not a verdict." in footer, "Menu: the standing verdict line renders")


def _search_and_open(page, query: str) -> None:
    """Find's own free-text search (`.st-key-seed_query`): fill, commit with
    Enter (a bare `.fill()` leaves the debounced value unsent -- pre-trim
    lesson, still true), settle. A single-hit query auto-selects (confirmed
    live for "Ifremer" against this index -- no `seed_pick` selectbox
    appears); a multi-hit query would need an extra `seed_pick` pick, which
    this file's own reference queries never trigger."""
    box = page.locator(".st-key-seed_query input").first
    box.click(timeout=ACTION_TIMEOUT_MS)
    box.fill(query)
    box.press("Enter")
    _settle(page, 3000)
    if page.locator(".st-key-profile").count() == 0 and page.locator(".st-key-seed_pick").count():
        page.locator(".st-key-seed_pick").click(timeout=ACTION_TIMEOUT_MS)
        page.wait_for_selector('[role="option"]', timeout=ACTION_TIMEOUT_MS)
        page.locator('[role="option"]').first.click(timeout=ACTION_TIMEOUT_MS)
        _settle(page, 3000)


def check_find(page) -> None:
    page.goto(f"{BASE_URL}/Find", wait_until="domcontentloaded")
    page.wait_for_selector(".st-key-seed_query", state="attached", timeout=ACTION_TIMEOUT_MS)
    _settle(page, 1500)
    _no_exception(page, "Find (empty)")
    check(page.locator(".st-key-seed_query").count() == 1, "Find: the search box renders")

    _search_and_open(page, "Ifremer")
    check(page.locator(".st-key-profile").count() == 1, "Find: searching 'Ifremer' opens the profile")
    _no_exception(page, "Find (Ifremer profile)")

    # --- 8 KPI tiles, incl. Star papers / Topics led, all non-empty --------
    tiles = page.locator(".st-key-profile .benchup-kpi")
    n_tiles = tiles.count()
    check(n_tiles == 8, f"Find: 8 KPI tiles render on the profile header (found {n_tiles})")
    tile_texts = tiles.all_text_contents()
    for label in FIND_KPI_LABELS:
        hit = next((t for t in tile_texts if t.startswith(label)), None)
        check(hit is not None, f"Find: the {label!r} tile renders")
        check(bool(hit) and len(hit) > len(label), f"Find: the {label!r} tile carries a non-empty value")

    # --- both radios (rendered as sidebar selectboxes) with the right options
    tree_opts = _select_options_text(page, "tree")
    check(set(tree_opts) == set(TREE_LABELS.values()),
          f"Find: the taxonomy control offers original/conservative/bestfit ({tree_opts})")
    basis_opts = _select_options_text(page, "basis")
    check(set(basis_opts) == set(BASIS_LABELS.values()),
          f"Find: the counting-basis control offers fractional/full ({basis_opts})")

    # --- all 6 (tree, basis) scenario combos render with no exception ------
    for tree in ("original", "conservative", "bestfit"):
        _open_select(page, "tree")
        _pick_option(page, TREE_LABELS[tree])
        _settle(page, 2500)
        for basis in ("frac", "full"):
            _open_select(page, "basis")
            _pick_option(page, BASIS_LABELS[basis])
            _settle(page, 2500)
            _no_exception(page, f"Find scenario tree={tree} basis={basis}")
    # restore the default combo for the checks below
    _open_select(page, "tree")
    _pick_option(page, TREE_LABELS["bestfit"])
    _settle(page, 2000)
    _open_select(page, "basis")
    _pick_option(page, BASIS_LABELS["frac"])
    _settle(page, 2500)

    # --- ERC profile panel (one of the five collapsed profile panels) ------
    erc_summary = page.locator(".st-key-panel_erc summary")
    check(erc_summary.count() == 1, "Find: the 'ERC profile' panel expander renders")
    erc_summary.click(timeout=ACTION_TIMEOUT_MS)
    _settle(page, 1500)
    check("ERC profile" in _full_page_text(page), "Find: the opened ERC panel shows its title")
    erc_traces = page.evaluate(
        "(() => { const el = document.querySelector('.st-key-fig_erc .js-plotly-plot');"
        " return el && el.data ? el.data.length : -1; })()")
    check(erc_traces > 0, f"Find: the ERC panel's plotly figure renders with data (n_traces={erc_traces})")
    sort_erc_options = page.locator(".st-key-sort_erc [data-testid='stRadioOption']")
    check(sort_erc_options.count() == 2,
          f"Find: the ERC panel's sort control renders (found {sort_erc_options.count()} options)")
    _no_exception(page, "Find (ERC panel)")

    # --- the topic planes: "Topics: volume, impact and frontier" panel ----
    topics_summary = page.locator(".st-key-panel_topic_planes summary")
    check(topics_summary.count() == 1, "Find: the topic-planes panel expander renders")
    topics_summary.click(timeout=ACTION_TIMEOUT_MS)
    _settle(page, 1500)
    check("Topics: volume, impact and frontier" in _full_page_text(page),
          "Find: the opened topic-planes panel shows its title")
    plane_a_traces = page.evaluate(
        "(() => { const el = document.querySelector('.st-key-fig_plane_impact .js-plotly-plot');"
        " return el && el.data ? el.data.length : -1; })()")
    check(plane_a_traces > 0, f"Find: plane A (volume/impact) renders with data (n_traces={plane_a_traces})")
    plane_b_traces = page.evaluate(
        "(() => { const el = document.querySelector('.st-key-fig_plane_frontier .js-plotly-plot');"
        " return el && el.data ? el.data.length : -1; })()")
    check(plane_b_traces > 0, f"Find: plane B (frontier) renders with data (n_traces={plane_b_traces})")
    topic_mode_options = page.locator(".st-key-topic_mode button[data-variant='segmented_control']")
    check(topic_mode_options.count() == 5,
          f"Find: the 'Topics shown' selector offers 5 modes (found {topic_mode_options.count()})")
    check(page.locator(".st-key-topic_n").count() == 1, "Find: the topics-shown slider renders")
    check(page.locator(".st-key-topic_fwci_stat").count() == 1, "Find: the FWCI mean/median radio renders")
    _no_exception(page, "Find (topic planes panel)")

    # --- lens tabs present and switchable -----------------------------------
    tabs = page.locator('[data-testid="stTab"]')
    n_tabs = tabs.count()
    check(n_tabs >= 3, f"Find: the lens tab strip renders (>=3 tabs, found {n_tabs})")
    tab_labels = tabs.all_text_contents()
    check(tab_labels[0] == "Overview", f"Find: the first tab is 'Overview' ({tab_labels[:3]})")
    check(tab_labels[-1].endswith("Aspirational"), f"Find: the last tab is Aspirational ({tab_labels[-1]!r})")
    before_panel = page.locator('[data-testid="stTabPanel"]').first.text_content()
    tabs.nth(1).click(timeout=ACTION_TIMEOUT_MS)
    _settle(page, 2000)
    after_panel = page.locator('[data-testid="stTabPanel"]').first.text_content()
    check(before_panel != after_panel, "Find: clicking a lens tab swaps the panel content")
    tabs.nth(0).click(timeout=ACTION_TIMEOUT_MS)
    _settle(page, 1500)

    # --- one workbook, 14 sheets --------------------------------------------
    dl_btn = page.locator('button').filter(has_text=re.compile(r"^Download"))
    check(dl_btn.count() >= 1, "Find: a 'Download' button renders at the foot of the page")
    with page.expect_download(timeout=120_000) as info:
        dl_btn.first.click(timeout=ACTION_TIMEOUT_MS)
    raw = Path(info.value.path()).read_bytes()
    check(raw[:2] == b"PK", "Find workbook: downloads as a real xlsx container")
    book = openpyxl.load_workbook(io.BytesIO(raw))
    check(len(book.sheetnames) == FIND_XLSX_SHEET_COUNT,
          f"Find workbook: {FIND_XLSX_SHEET_COUNT} sheets (found {len(book.sheetnames)}: {book.sheetnames})")
    check(book.sheetnames[:2] == ["Profile", "Overview"],
          f"Find workbook: sheet order starts Profile, Overview ({book.sheetnames[:2]})")
    _no_exception(page, "Find (end of checks)")


def check_compare_deeplink(page) -> None:
    page.goto(f"{BASE_URL}/Compare?compare={IFREMER_ID},{NIOZ_ID}", wait_until="domcontentloaded")
    page.wait_for_selector(".st-key-compare_slot_0", state="attached", timeout=60_000)
    _settle(page, 3000)
    _no_exception(page, "Compare (deep link)")

    # --- both slots filled by NAME (never the raw OpenAlex id) -------------
    slot0 = _selectbox_value(page, "compare_slot_0")
    slot1 = _selectbox_value(page, "compare_slot_1")
    check("Ifremer" in slot0, f"Compare deep link: slot 1 shows the NAME 'Ifremer' (got {slot0!r})")
    check("I" != slot1[:1] or not slot1[1:].isdigit(),
          f"Compare deep link: slot 2 does not show a raw institution id ({slot1!r})")
    check(len(slot1) > 3, f"Compare deep link: slot 2 shows a real name (got {slot1!r})")

    # --- every section header present ---------------------------------------
    headings = page.locator('[data-testid="stHeading"]').all_text_contents()
    missing = [h for h in COMPARE_SECTION_HEADERS if h not in headings]
    check(not missing, f"Compare: every section header renders ({missing or 'all present'}; got {headings})")

    # --- the relationship's three tiles + the always-visible evidence line -
    n_tiles = page.locator('div[class*="benchup-kpi"]').count()
    check(n_tiles == 21, f"Compare: 18 card tiles + 3 relationship tiles render (found {n_tiles})")
    body_text = page.locator("body").inner_text()
    for label in COMPARE_TILE_LABELS:
        check(label in body_text, f"Compare: relationship tile {label!r} renders")
    check("joint articles" in body_text, "Compare: the momentum evidence line renders (every state says so)")
    check(page.locator('[class*="st-key-fig_reciprocity"] .js-plotly-plot').count() >= 1,
          "Compare: the reciprocity scatter renders")

    # --- Profile/Impact tabs present and switchable (Thematic shape) -------
    # DOM FACT: Compare renders TWO separate st.tabs() widgets with the SAME
    # two labels (Thematic shape's own, then SDG's own) -- `[data-testid=
    # "stTabPanel"]`'s FIRST element in DOM stays the Thematic-shape
    # section's own "Profile" panel node regardless of which tab is active
    # (a textContent diff against `.first` never changes), so the switch is
    # instead verified against the chart's own per-tab key
    # (`charts_compare.two_tab_bars`'s caller keys each tab's own figure
    # `fig_shape_profile` / `fig_shape_impact`, `views_compare.py`).
    shape_tabs = page.locator('[data-testid="stTab"]')
    tab_labels = shape_tabs.all_text_contents()
    check(all(lbl in tab_labels for lbl in COMPARE_TAB_LABELS),
          f"Compare: Profile/Impact tabs render ({set(COMPARE_TAB_LABELS) - set(tab_labels)} missing)")
    check(page.locator('[class*="st-key-fig_shape_profile"] .js-plotly-plot').count() >= 1,
          "Compare: the Thematic-shape Profile chart renders by default")
    first_impact_tab = shape_tabs.filter(has_text="Impact").first
    if first_impact_tab.count():
        first_impact_tab.click(timeout=ACTION_TIMEOUT_MS)
        _settle(page, 2500)
        check(page.locator('[class*="st-key-fig_shape_impact"] .js-plotly-plot').count() >= 1,
              "Compare: clicking the Impact tab renders the Thematic-shape Impact chart")
        shape_tabs.filter(has_text="Profile").first.click(timeout=ACTION_TIMEOUT_MS)
        _settle(page, 1500)

    # --- topic overlap: the shared selector, the owner-coloured
    #     plane, the balance bars -- replaces the retired mirror chart and
    #     its "Show all" interaction entirely (no such button exists any
    #     more on this page).
    overlap_mode_options = page.locator(".st-key-compare_topic_mode button[data-variant='segmented_control']")
    check(overlap_mode_options.count() == 5,
          f"Compare: the 'Topics shown' selector offers 5 modes (found {overlap_mode_options.count()})")
    check(page.locator(".st-key-compare_topic_n").count() == 1, "Compare: the topics-per-institution slider renders")
    check(page.locator(".st-key-compare_topic_fwci_stat").count() == 1, "Compare: the FWCI mean/median radio renders")
    overlap_plane_sel = '[class*="st-key-fig_topic_overlap_plane"]'
    overlap_bars_sel = '[class*="st-key-fig_topic_overlap_bars"]'
    page.wait_for_selector(f"{overlap_bars_sel} .js-plotly-plot", state="attached", timeout=60_000)
    _settle(page, 1500)
    check(page.locator(overlap_plane_sel).count() >= 1, "Compare: the topic-overlap owner-coloured plane renders")
    check(page.locator(overlap_bars_sel).count() >= 1, "Compare: the topic-overlap balance bars render")
    check("Joint" in _full_page_text(page), "Compare: the topic-overlap legend names the 'Joint' chip")
    _no_exception(page, "Compare (topic overlap)")

    # --- the topic-overlap table: 18 columns (the retired shared-frontier
    #     table's own 17, plus "Held by") -- SOFTENED to a structural proof
    #     (see module docstring: glide-data-grid's a11y mirror only ever
    #     exposed the first 3 (of N) columnheaders live, even after a
    #     scrollLeft write and a synthetic wheel scroll over the canvas --
    #     the LEFT columns, never the link columns at the right, came back).
    page.wait_for_selector('[role="grid"]', state="attached", timeout=30_000)
    _settle(page, 800)
    grid = page.locator('[role="grid"]').first
    check(grid.count() >= 1, "Compare: the topic-overlap table renders as an accessible grid")
    if grid.count():
        colcount = grid.get_attribute("aria-colcount")
        check(colcount == "18",
              f"Compare table: aria-colcount == 18 (topic..url_joint, the 3 link columns included) (got {colcount})")
    src = (APP_DIR / "lib" / "views_compare.py").read_text(encoding="utf-8")
    n_link_cols = src.count("st.column_config.LinkColumn(")
    check(n_link_cols == 3, f"Compare table (source proof): exactly 3 LinkColumn columns are configured "
                            f"(institution A, institution B, joint) (found {n_link_cols})")
    soften("Compare table 3-link-column check reads aria-colcount (18, live) + a LinkColumn( source "
          "count (3, static) rather than live column-header text: glide-data-grid's accessibility "
          "mirror only exposes the columns scrolled into the canvas viewport, and neither scrollLeft "
          "nor a synthetic wheel event over the canvas brought the 3 rightmost (link) columns into it "
          "in a live trial")

    # --- one workbook, 6 sheets ----------------------------------------------
    dl_btn = page.locator('button').filter(has_text=re.compile(r"^Download this view"))
    check(dl_btn.count() >= 1, "Compare: the 'Download this view (Excel)' button renders")
    with page.expect_download(timeout=120_000) as info:
        dl_btn.first.click(timeout=ACTION_TIMEOUT_MS)
    raw = Path(info.value.path()).read_bytes()
    book = openpyxl.load_workbook(io.BytesIO(raw))
    check(book.sheetnames == COMPARE_XLSX_SHEETS,
          f"Compare workbook: 6 sheets in order ({book.sheetnames})")

    # --- share box -----------------------------------------------------------
    code_texts = page.evaluate("Array.from(document.querySelectorAll('code')).map(c => c.textContent)")
    expected = f"?compare={IFREMER_ID},{NIOZ_ID}"
    check(expected in code_texts, f"Compare: the share box reads exactly {expected!r} (found {code_texts})")
    _no_exception(page, "Compare (end of deep-link checks)")


def check_compare_deeplink_pre_show_all_workbook(page) -> None:
    """A SEPARATE fresh session: the download-button lesson (memory:
    streamlit-rerun-breaks-download-button) re-checked against the
    topic-overlap controls that replaced the retired 'Show all' button --
    changing the 'Topics shown' selector must not poison
    `st.download_button` for the rest of the session. Isolated in its own
    session so a failure here is legible on its own, the same reason the
    retired before/after Show-all split used two sessions."""
    page.goto(f"{BASE_URL}/Compare?compare={IFREMER_ID},{NIOZ_ID}", wait_until="domcontentloaded")
    page.wait_for_selector(".st-key-compare_slot_0", state="attached", timeout=60_000)
    _settle(page, 3000)
    led_option = page.locator(".st-key-compare_topic_mode button[data-variant='segmented_control']") \
        .filter(has_text="Topics led")
    if led_option.count():
        led_option.first.click(timeout=ACTION_TIMEOUT_MS)
        _settle(page, 2000)
        _no_exception(page, "Compare (after changing the topic-overlap selector)")
    dl_btn = page.locator('button').filter(has_text=re.compile(r"^Download this view"))
    with page.expect_download(timeout=120_000) as info:
        dl_btn.first.click(timeout=ACTION_TIMEOUT_MS)
    raw = Path(info.value.path()).read_bytes()
    book = openpyxl.load_workbook(io.BytesIO(raw))
    check(book.sheetnames == COMPARE_XLSX_SHEETS,
          f"Compare workbook (after changing the topic-overlap selector): 6 sheets in order ({book.sheetnames})")
    dl_buttons_still_present = page.locator('button').filter(has_text=re.compile(r"^Download this view"))
    check(dl_buttons_still_present.count() >= 1,
          "Compare: the download button is still present after the selector change")


def check_compare_clear(page) -> None:
    page.goto(f"{BASE_URL}/Compare?compare={IFREMER_ID},{NIOZ_ID}", wait_until="domcontentloaded")
    page.wait_for_selector(".st-key-compare_slot_0", state="attached", timeout=60_000)
    _settle(page, 3000)
    page.locator(".st-key-compare_slot_clear_0 button").first.click(timeout=ACTION_TIMEOUT_MS)
    _settle(page, 2500)
    slot0 = _selectbox_value(page, "compare_slot_0")
    check(slot0 == SLOT_EMPTY_LABEL, f"Compare Clear: slot 1 empties (shows {SLOT_EMPTY_LABEL!r}, got {slot0!r})")
    check(PROMPT_NEED_TWO in _full_page_text(page),
          f"Compare Clear: the page falls back to the pick-two prompt ({PROMPT_NEED_TWO!r})")


def check_compare_seeding(page) -> None:
    """Find -> Compare, real in-app navigation only (no `page.goto` between
    the two -- see module docstring): open Find, search+pick Ifremer, click
    the Compare nav link, assert slot 1 == Ifremer."""
    page.goto(BASE_URL, wait_until="domcontentloaded")
    _click_nav(page, "Find")
    check("/Find" in page.url, f"Seeding: nav click opened Find ({page.url})")
    _search_and_open(page, "Ifremer")
    check(page.locator(".st-key-profile").count() == 1, "Seeding: Find opened the Ifremer profile")
    _click_nav(page, "Compare")
    check("/Compare" in page.url, f"Seeding: nav click opened Compare ({page.url})")
    _settle(page, 1500)
    slot0 = _selectbox_value(page, "compare_slot_0")
    check("Ifremer" in slot0, f"Seeding: Compare's slot 1 pre-fills with Ifremer from Find (got {slot0!r})")


def check_methods(page) -> None:
    page.goto(f"{BASE_URL}/Methods", wait_until="domcontentloaded")
    page.wait_for_selector('[data-testid="stExpander"]', state="attached", timeout=ACTION_TIMEOUT_MS)
    _settle(page, 2000)
    _no_exception(page, "Methods")
    check("How it is built" in _full_page_text(page), "Methods: the page title renders")

    summaries = page.locator('[data-testid="stExpander"] summary')
    n = summaries.count()
    check(n == len(METHODS_SECTION_TITLES),
          f"Methods: {len(METHODS_SECTION_TITLES)} expanders render (found {n})")
    # DOM FACT (live-verified): each summary's textContent is prefixed with
    # the expander's chevron ICON LIGATURE text ("keyboard_arrow_right") --
    # substring containment, never list equality, against the raw text.
    titles = [t.strip() for t in summaries.all_text_contents()]
    for title in METHODS_SECTION_TITLES:
        check(any(title in t for t in titles), f"Methods: the {title!r} section renders (titles: {titles})")

    # open one expander and confirm its body carries real (non-template) text
    summaries.first.click(timeout=ACTION_TIMEOUT_MS)
    _settle(page, 1200)
    body_text = page.locator('[data-testid="stExpander"]').first.text_content()
    check(bool(body_text) and "{" not in body_text,
          "Methods: an opened section's body has every {placeholder} filled at run time")

    dl_btn = page.locator('button').filter(has_text="Download the source note")
    check(dl_btn.count() >= 1, "Methods: the source-note download button renders")
    with page.expect_download(timeout=60_000) as info:
        dl_btn.first.click(timeout=ACTION_TIMEOUT_MS)
    raw = Path(info.value.path()).read_bytes()
    check(len(raw) > 500, f"Methods: METHODS_NOTE.md downloads with real content ({len(raw)} bytes)")
    _no_exception(page, "Methods (end of checks)")


# ------------------------------------------------------------- widths -------

WIDTH_TARGETS = [
    ("Menu", ""),
    ("Find", f"/Find?seed={IFREMER_ID}"),
    ("Compare", f"/Compare?compare={IFREMER_ID},{NIOZ_ID}"),
    ("Methods", "/Methods"),
]


def check_widths(browser) -> None:
    for label, suffix in WIDTH_TARGETS:
        for width in WIDTHS:
            page = browser.new_page(viewport={"width": width, "height": 1000})
            page.set_default_timeout(ACTION_TIMEOUT_MS)
            try:
                page.goto(f"{BASE_URL}{suffix}", wait_until="domcontentloaded")
                page.wait_for_timeout(3500)
                scroll, inner = _scroll_width_ok(page)
                check(scroll <= inner + 2,
                     f"{label} {width}px: scrollWidth {scroll} <= innerWidth+2 {inner + 2}")
            except Exception as exc:  # noqa: BLE001
                fail_section(f"{label} {width}px width check", exc)
            finally:
                page.close()


# -------------------------------------------------------------------- main --

SECTIONS = ["menu", "find", "compare", "methods", "widths"]


def _run(sections: list[str]) -> None:
    global PORT, BASE_URL
    server = _start_server(APP_DIR, PORT)
    try:
        if not _wait_for_port(PORT):
            check(False, f"server did not open port {PORT}")
            return
        with sync_playwright() as p:
            browser = p.chromium.launch()
            context = browser.new_context(viewport={"width": 1280, "height": 1000}, accept_downloads=True)
            page = context.new_page()
            page.set_default_timeout(ACTION_TIMEOUT_MS)

            if "menu" in sections:
                try:
                    check_menu(page)
                except Exception as exc:  # noqa: BLE001
                    fail_section("Menu", exc)

            if "find" in sections:
                try:
                    check_find(page)
                except Exception as exc:  # noqa: BLE001
                    fail_section("Find", exc)

            if "compare" in sections:
                try:
                    check_compare_deeplink(page)
                except Exception as exc:  # noqa: BLE001
                    fail_section("Compare deep link", exc)
                try:
                    check_compare_deeplink_pre_show_all_workbook(page)
                except Exception as exc:  # noqa: BLE001
                    fail_section("Compare workbook (after selector change)", exc)
                try:
                    check_compare_clear(page)
                except Exception as exc:  # noqa: BLE001
                    fail_section("Compare Clear", exc)
                try:
                    check_compare_seeding(page)
                except Exception as exc:  # noqa: BLE001
                    fail_section("Compare seeding from Find", exc)

            if "methods" in sections:
                try:
                    check_methods(page)
                except Exception as exc:  # noqa: BLE001
                    fail_section("Methods", exc)

            page.close()
            context.close()

            if "widths" in sections:
                try:
                    check_widths(browser)
                except Exception as exc:  # noqa: BLE001
                    fail_section("Width sweep", exc)

            browser.close()
    finally:
        _stop_server(server)


def main() -> int:
    global PORT, BASE_URL
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8611)
    parser.add_argument("--sections", type=str, default=",".join(SECTIONS),
                        help="comma-separated subset of: " + ",".join(SECTIONS))
    args = parser.parse_args()
    PORT = args.port
    BASE_URL = f"http://127.0.0.1:{PORT}"
    sections = [s.strip() for s in args.sections.split(",") if s.strip()]

    _run(sections)

    failed = [m for ok, m in RESULTS if not ok]
    print(f"\n{len(RESULTS) - len(failed)}/{len(RESULTS)} checks passed")
    if FINDINGS:
        print(f"\n{len(FINDINGS)} app finding(s) (outside this suite's scope):")
        for m in FINDINGS:
            print(" -", m)
    if SOFTENED:
        print(f"\n{len(SOFTENED)} check(s) softened (see reason above each):")
        for m in SOFTENED:
            print(" -", m)
    if failed:
        print(f"\n{len(failed)} FAILED:")
        for m in failed:
            print(" - FAILED:", m)
        return 1
    print("ALL CHECKS PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
