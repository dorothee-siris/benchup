"""
tests/stress/run_stress.py -- the permanent memory
stress gate. Drives the REAL Streamlit app (one `streamlit run Menu.py` server,
headless) through a deterministic crash-path replay (phase A) and randomised
concurrent chaos (phase B) while sampling the server's own python.exe RSS every
0.5s, then reports peak/mean/final per phase against the ceiling (< 1,800 MB,
half the 2.7 GB Community Cloud cap) and "the server never died".

Method follows an earlier stress harness's approach: sample the
STREAMLIT SERVER'S OWN python.exe (not the Playwright/Chromium client) via
`ops/rss_probe.py` (stdlib ctypes, no psutil -- it is not a dependency of this
app and must not become one for a test-only need).

PID resolution (verified empirically before trusting it):
`subprocess.Popen([PYTHON, "-m", "streamlit", "run", ...])` does NOT give the
real server's PID on this Windows box -- `proc.pid` stays a ~5 MB launcher for
the process lifetime while Streamlit's own bootstrap spawns a SEPARATE CHILD
python.exe that does the actual serving (confirmed with `Get-CimInstance
Win32_Process -Filter "ParentProcessId=<proc.pid>"`; the child even resolves a
different `python.exe` off PATH than `sys.executable`, not just a different
PID). Sampling `proc.pid` directly reads a flat ~5 MB line for the whole run --
a silent false PASS, not a "server did not start" failure, so this could not be
caught by "PID not openable" alone. The fix: after the port opens, resolve the
PID that is actually `LISTENING` on it via `netstat -ano` (stdlib subprocess
call to a Windows built-in, no new dependency) -- correct regardless of
whether Streamlit's server ends up being the launched process itself (`proc.
pid`) or a child, which is exactly the ambiguity the BUILD_PLAN brief flags
("on Windows `streamlit run` may itself be the python process; verify with the
PID you spawned"). `stop_server` below terminates BOTH `proc.pid` and the
resolved server PID (if different) so no orphan is ever left behind.

Environment passthrough (`os.environ.copy()`, not a fresh env) is what lets the
broken-control run (BUILD_PLAN.md D12/T1 acceptance item 3) work with NO code
change here: `BENCHUP_SCENARIO_ENTRIES=3 python tests/stress/run_stress.py
--phases A,B --minutes 4` raises the resident scenario cache from 1 to 3 in the
spawned server and the harness should show a visibly higher peak -- proving this
script actually exercises scenario switches rather than measuring something else
(see tests/stress/README.md "Broken control").

Phase C (bare-process six-scenario cycle, no browser, no server) lives in the
sibling script `cycle_scenarios.py` -- run it standalone, or include "C" in
--phases here to have this script shell out to it and fold its numbers into the
same report.

Usage:
    python tests/stress/run_stress.py --minutes 10 --sessions 3 --phases A,B,C \
        --out ../evals/stress/
"""
from __future__ import annotations

import argparse
import csv
import os
import random
import socket
import subprocess
import sys
import threading
import time
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

STRESS_DIR = Path(__file__).resolve().parent          # app/tests/stress
APP_DIR = STRESS_DIR.parents[1]                        # app/
sys.path.insert(0, str(APP_DIR / "ops"))
from rss_probe import process_rss_mb  # noqa: E402

PYTHON = sys.executable
CYCLE_SCRIPT = STRESS_DIR / "cycle_scenarios.py"

PEAK_CEILING_MB = 1800.0  # half the 2.7 GB Community Cloud cap

# ---------------------------------------------------------------- seeds -----
# The same 12 institutions the reference goldens use --
# 5 fixed anchors + 7 already vetted for type/size variety, so
# this harness never re-derives its own sample from index.parquet. Search text
# is the exact `display_name` (see search.py: a whole-field match is ALWAYS
# "exact" priority, so a full legal name reliably auto-selects with one hit --
# no dropdown interaction needed for most of these in the chaos loop).
SEEDS = [
    ("I154202486", "Ifremer"),
    ("I4210107283", "Royal Netherlands Institute for Sea Research"),
    ("I35440088", "ETH Zurich"),
    ("I1294671590", "Centre National de la Recherche Scientifique"),
    ("I68947357", "Université de Strasbourg"),
    ("I4210143826", "Institut National des Sciences Appliquées Centre Val de Loire"),
    ("I142910587", "University of Salento"),
    ("I4210086484", "HIA du Val-de-Grâce à Paris"),
    ("I4210149564", "Ospedale SS. Annunziata"),
    ("I4210150693", "The Medical Device (United Kingdom)"),
    ("I4210131494", "Ministère de l'Enseignement Supérieur, de la Recherche et de l'Espace"),
    ("I4210142177", "Pfizer-University of Granada-Junta de Andalucía Centre for Genomics and "
                    "Oncological Research"),
]
SEED_IDS = [s[0] for s in SEEDS]

# lib/copy.py TREE_LABELS / BASIS_LABELS values (the format_func text the
# sidebar selectboxes actually render -- read live off lib/copy.py, not
# guessed; confirmed against the running app before this script was written).
TREE_OPTION_LABELS = [
    "OpenAlex taxonomy as published",
    "Repaired taxonomy (conservative)",
    "Repaired taxonomy (best fit, default)",
]
BASIS_OPTION_LABELS = ["Fractional counting", "Full counting"]

TREE_COMBOBOX_LABEL = "Subject taxonomy"
BASIS_COMBOBOX_LABEL = "Counting basis"
SEED_SEARCH_LABEL = "Institution name, acronym or alternative name"
SEED_PICK_COMBOBOX_LABEL = "Institution to profile"

# Actual rendered button text (confirmed live -- lib/copy.py's FIND/COMPARE
# EXPORT_XLSX_BUTTON constants are NOT what render for Compare; views_compare.py
# reads a different key. Two distinct strings, one per page).
FIND_DOWNLOAD_LABEL = "Download this profile and benchmark (Excel)"
COMPARE_DOWNLOAD_LABEL = "Download this view (Excel)"

MAIN_SCROLL_CONTAINER = '[data-testid="stMain"]'
STATUS_WIDGET = '[data-testid="stStatusWidget"]'


# ------------------------------------------------------------- server -----

def _wait_for_port(port: int, timeout: float = 90.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            if sock.connect_ex(("127.0.0.1", port)) == 0:
                return True
        time.sleep(0.5)
    return False


def _find_listening_pid(port: int, timeout: float = 30.0) -> int | None:
    """The real server PID: whichever process `netstat -ano` shows LISTENING
    on `port` -- NOT necessarily `proc.pid` (see module docstring). Windows
    `netstat` output line shape: `  TCP    0.0.0.0:8651    0.0.0.0:0    LISTENING    12345`;
    PID is always the last whitespace-separated token."""
    needle = f":{port} "
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            # errors="replace": a French-locale Windows console emits `netstat`'s
            # header row (accented "Numéro") in the OEM codepage, not the ANSI
            # codepage Python's text-mode decode assumes -- observed to raise
            # UnicodeDecodeError deep in `communicate()`'s own reader thread
            # (silently leaves `.stdout` None, not a catchable exception here)
            # before this `errors="replace"` was added. The PID column is
            # plain ASCII digits regardless, so a replaced header byte never
            # touches the value this function actually reads.
            out = subprocess.run(["netstat", "-ano"], capture_output=True, text=True,
                                 errors="replace", timeout=10).stdout or ""
        except Exception:  # noqa: BLE001
            out = ""
        for line in out.splitlines():
            if "LISTENING" in line and needle in line and line.strip().startswith("TCP"):
                parts = line.split()
                try:
                    return int(parts[-1])
                except ValueError:
                    continue
        time.sleep(0.5)
    return None


def start_server(port: int, log_path: Path) -> subprocess.Popen:
    """One `streamlit run Menu.py` server. `env=os.environ.copy()` (not a
    fresh dict) is the passthrough the broken-control run depends on:
    `BENCHUP_SCENARIO_ENTRIES` set by the CALLER before invoking this script
    reaches `lib/engine/scenario_cache.py`'s own `os.environ.get(...)` read
    unchanged. `-m streamlit run` (never a bare `streamlit` console-script
    call) so `proc.pid` is the interpreter itself on Windows where Streamlit
    does not spawn a child (see module docstring; `_find_listening_pid`
    resolves the real one when it does).

    stdout/stderr go to a FILE, never `subprocess.PIPE` left undrained: the
    app's own build-time code prints during every scenario build (confirmed --
    `cycle_scenarios.py`'s "[substrates] _load_topic_share(...)" lines), and
    repeatedly cycling basis/taxonomy (exactly what phase A does) produces
    enough of it to fill an unread pipe's OS buffer. Once full, the
    process's own `write()` calls BLOCK -- the whole server hangs, every
    request past that point stalls or the accept loop itself stops turning,
    which reads exactly like "the server died" downstream (timeouts, then
    `ERR_CONNECTION_REFUSED`). Measured hitting this on the very first
    version of this script -- a file has no such buffer
    limit, and doubles as a server log worth keeping on a FAIL."""
    log_f = open(log_path, "w", encoding="utf-8", errors="replace")
    return subprocess.Popen(
        [PYTHON, "-m", "streamlit", "run", "Menu.py",
         "--server.headless", "true", "--server.port", str(port)],
        cwd=str(APP_DIR), stdout=log_f, stderr=subprocess.STDOUT,
        env=os.environ.copy(),
    )


def _taskkill(pid: int) -> None:
    try:
        subprocess.run(["taskkill", "/F", "/PID", str(pid)], capture_output=True,
                       text=True, errors="replace", timeout=10)
    except Exception:  # noqa: BLE001
        pass


def stop_server(proc: subprocess.Popen, server_pid: int | None) -> None:
    """Never leaves a server behind, even on a mid-run exception (caller's
    `finally`): terminate the LAUNCHED process (`proc.pid`), then -- since
    that PID and the real server PID can differ on Windows (module docstring)
    -- also `taskkill` the resolved `server_pid` if it is a different, still-
    running PID. Belt and braces: `proc.terminate()` alone was observed to
    leave the real child (and its RAM) running as an orphan."""
    if proc.poll() is None:
        proc.terminate()
        try:
            proc.wait(timeout=10)
        except subprocess.TimeoutExpired:
            proc.kill()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                pass
    if server_pid is not None and server_pid != proc.pid:
        if process_rss_mb(server_pid) is not None:  # still openable => still alive
            _taskkill(server_pid)


# --------------------------------------------------------- RSS sampler -----

class RssSampler:
    """Background thread sampling the server's WorkingSetSize every
    `interval` seconds into `samples` as (elapsed_s, phase, rss_mb). A
    `process_rss_mb` miss (PID no longer openable) is the ONE reliable "the
    server died" signal -- ctypes `OpenProcess` fails only when the process
    is gone (BUILD_PLAN.md T1 spec: "server alive at the end ... PID still
    running") -- recorded once as `died_at`, never silently dropped as a
    zero or skipped as noise."""

    def __init__(self, pid: int, interval: float = 0.5):
        self.pid = pid
        self.interval = interval
        self.samples: list[tuple[float, str, float]] = []
        self.phase = "init"
        self.died_at: float | None = None
        self._stop = threading.Event()
        self._t0 = time.time()
        self._thread: threading.Thread | None = None

    def set_phase(self, name: str) -> None:
        self.phase = name

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def _run(self) -> None:
        while not self._stop.is_set():
            t = time.time() - self._t0
            r = process_rss_mb(self.pid)
            if r is None:
                if self.died_at is None:
                    self.died_at = t
            else:
                self.samples.append((t, self.phase, r[0]))
            time.sleep(self.interval)

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=5)

    def phase_stats(self, phase: str) -> dict:
        vals = [mb for _, p, mb in self.samples if p == phase]
        if not vals:
            return {"peak": None, "mean": None, "final": None, "n": 0}
        return {"peak": max(vals), "mean": sum(vals) / len(vals), "final": vals[-1], "n": len(vals)}


# ------------------------------------------------------------- helpers -----

def wait_idle(page, timeout_ms: int = 120_000) -> bool:
    """Phase A ONLY (per spec): poll for Streamlit's running/status widget
    to clear after an action, instead of a fixed sleep, so each step in the
    deterministic replay actually waits for the scenario build it triggered
    to finish before the next one starts."""
    page.wait_for_timeout(150)  # let the rerun actually start
    deadline = time.time() + timeout_ms / 1000
    while time.time() < deadline:
        try:
            if page.locator(STATUS_WIDGET).count() == 0:
                return True
        except Exception:
            return False
        time.sleep(0.2)
    return False


def has_error_box(page) -> bool:
    """A Streamlit uncaught-exception box always titles itself "Oh no." --
    the one page-content signal for "a failure to record" the brief names
    for phase B, alongside a websocket disconnect (caught as a raised
    Playwright exception at the call site instead -- there is no reliable
    DOM signal for that one)."""
    try:
        return page.get_by_text("Oh no", exact=False).count() > 0
    except Exception:
        return False


def pick_seed(page, query: str) -> None:
    """Type `query` into the seed search box; if it is not a unique hit
    (search.py: multiple entries share this text), open the resulting
    picker combobox and take its first (highest-ranked) option -- the same
    interaction a real multi-hit search forces on a reader."""
    box = page.get_by_label(SEED_SEARCH_LABEL)
    box.fill(query)
    box.press("Enter")


def resolve_picker_if_present(page, rng: random.Random | None = None) -> None:
    picker = page.get_by_role("combobox", name=SEED_PICK_COMBOBOX_LABEL)
    if picker.count() == 0:
        return
    picker.first.click()
    page.wait_for_timeout(150)
    opts = page.get_by_role("option")
    n = opts.count()
    if n == 0:
        return
    idx = rng.randrange(n) if rng is not None else 0
    opts.nth(idx).click()


def set_combobox(page, label: str, option_text: str) -> bool:
    box = page.get_by_role("combobox", name=label)
    if box.count() == 0:
        return False
    box.first.click()
    page.wait_for_timeout(150)
    opt = page.get_by_role("option", name=option_text)
    if opt.count() == 0:
        # closed empty-handed -- press Escape so the popup does not eat the
        # next click
        page.keyboard.press("Escape")
        return False
    opt.first.click()
    return True


def scroll_main(page, y) -> None:
    main = page.locator(MAIN_SCROLL_CONTAINER)
    if main.count():
        main.first.evaluate(f"el => el.scrollTo(0, {y})")


def try_download(page, label: str, timeout_ms: int = 45_000):
    btn = page.get_by_role("button", name=label)
    if btn.count() == 0:
        return False, "button not found"
    try:
        with page.expect_download(timeout=timeout_ms) as dl_info:
            btn.first.click()
        return True, dl_info.value.suggested_filename
    except Exception as e:  # noqa: BLE001 -- chaos harness, every failure mode is a recorded result
        return False, str(e)


# --------------------------------------------------------------- phase A ----

def run_phase_a(page, base: str, sampler: RssSampler) -> list[dict]:
    """Deterministic replay of the measured crash path (BUILD_PLAN.md
    Trigger paragraph): open an institution, cycle basis and taxonomy
    (each swap evicts/rebuilds a whole scenario substrate dict under D11),
    visit Compare, come back, download. One continuous browser context --
    the "one browser context" the spec calls for. Every step is wrapped so
    one failure does not abort the rest (the report needs to know ALL step
    outcomes, not just the first one)."""
    sampler.set_phase("A")
    steps: list[dict] = []

    def step(name: str, fn) -> None:
        t0 = time.time()
        try:
            fn()
            steps.append({"step": name, "ok": True, "s": round(time.time() - t0, 2)})
        except Exception as e:  # noqa: BLE001
            steps.append({"step": name, "ok": False, "error": str(e)[:300],
                         "s": round(time.time() - t0, 2)})

    def _menu_to_find():
        page.goto(base, wait_until="networkidle")
        page.wait_for_timeout(500)
        page.get_by_role("link", name="Open Find peers").click()
        wait_idle(page)

    def _search_ifremer():
        pick_seed(page, "Ifremer")
        wait_idle(page)
        resolve_picker_if_present(page)
        wait_idle(page)

    def _basis(opt):
        assert set_combobox(page, BASIS_COMBOBOX_LABEL, opt), f"basis option {opt!r} not offered"
        wait_idle(page)

    def _tree(opt):
        assert set_combobox(page, TREE_COMBOBOX_LABEL, opt), f"tree option {opt!r} not offered"
        wait_idle(page)

    def _compare(a, b):
        page.goto(f"{base}/Compare?compare={a},{b}", wait_until="networkidle")
        wait_idle(page)
        scroll_main(page, 100000)

    def _find_again():
        page.goto(f"{base}/Find", wait_until="networkidle")
        wait_idle(page)
        pick_seed(page, "Ifremer")
        wait_idle(page)
        resolve_picker_if_present(page)
        wait_idle(page)

    def _download_find():
        ok, info = try_download(page, FIND_DOWNLOAD_LABEL)
        assert ok, f"Find workbook download failed: {info}"

    step("menu -> find", _menu_to_find)
    step("search 'Ifremer'", _search_ifremer)
    step("basis frac -> full", lambda: _basis("Full counting"))
    step("tree bestfit -> original", lambda: _tree("OpenAlex taxonomy as published"))
    step("tree original -> conservative", lambda: _tree("Repaired taxonomy (conservative)"))
    step("tree conservative -> bestfit", lambda: _tree("Repaired taxonomy (best fit, default)"))
    step("compare Ifremer x NIOZ", lambda: _compare("I154202486", "I4210107283"))
    step("find again", _find_again)
    step("basis switch (full -> frac default then -> full)", lambda: _basis("Full counting"))
    step("download Find workbook", _download_find)
    step("compare ETH x CNRS (different pair)", lambda: _compare("I35440088", "I1294671590"))

    return steps


# --------------------------------------------------------------- phase B ----

CHAOS_ACTIONS = ["find_seed", "scenario_combo", "compare_pair", "methods", "download", "scroll"]


def chaos_session(session_id: int, base: str, minutes: float, seed: int, out: dict) -> None:
    """One concurrent browser context/session (own `sync_playwright()`
    instance per thread -- Playwright's sync API supports this as long as
    each thread owns its instance, per its own docs; simpler and safer here
    than mixing threads with the async API). Randomised action loop, NO
    waiting for spinners -- only the 300-1500ms pause the spec names -- so
    this genuinely fires actions faster than the app can settle, the whole
    point of "chaos"."""
    rng = random.Random(seed * 1000 + session_id)
    deadline = time.time() + minutes * 60
    actions = 0
    failures: list[str] = []
    last_download = 0.0

    with sync_playwright() as p:
        browser = p.chromium.launch()
        context = browser.new_context(viewport={"width": 1280, "height": 900}, accept_downloads=True)
        page = context.new_page()
        try:
            page.goto(base, wait_until="commit")
        except Exception as e:  # noqa: BLE001
            failures.append(f"init: {e}")

        while time.time() < deadline:
            action = rng.choice(CHAOS_ACTIONS)
            try:
                if action == "find_seed":
                    _, name = rng.choice(SEEDS)
                    page.goto(f"{base}/Find", wait_until="commit")
                    pick_seed(page, name)
                    resolve_picker_if_present(page, rng)
                elif action == "scenario_combo":
                    set_combobox(page, TREE_COMBOBOX_LABEL, rng.choice(TREE_OPTION_LABELS))
                    set_combobox(page, BASIS_COMBOBOX_LABEL, rng.choice(BASIS_OPTION_LABELS))
                elif action == "compare_pair":
                    a, b = rng.sample(SEED_IDS, 2)
                    page.goto(f"{base}/Compare?compare={a},{b}", wait_until="commit")
                elif action == "methods":
                    page.goto(f"{base}/Methods", wait_until="commit")
                elif action == "download":
                    now = time.time()
                    if now - last_download >= 60:  # <= 1 / minute / session
                        last_download = now
                        for label in (FIND_DOWNLOAD_LABEL, COMPARE_DOWNLOAD_LABEL):
                            if page.get_by_role("button", name=label).count():
                                ok, info = try_download(page, label)
                                if not ok:
                                    failures.append(f"download[{label}]: {info}")
                                break
                elif action == "scroll":
                    scroll_main(page, rng.randint(0, 6000))

                actions += 1
                if has_error_box(page):
                    failures.append(f"error box after {action}")
                    page.goto(base, wait_until="commit")  # recover, don't let one crash sink the session
            except Exception as e:  # noqa: BLE001
                actions += 1
                failures.append(f"{action}: {str(e)[:200]}")
                try:
                    page.goto(base, wait_until="commit")
                except Exception:  # noqa: BLE001
                    pass  # even recovery failed; next loop iteration will record its own failure

            page.wait_for_timeout(rng.randint(300, 1500))

        browser.close()

    out[session_id] = {"actions": actions, "failures": failures, "n_failures": len(failures)}


def run_phase_b(base: str, sessions: int, minutes: float, seed: int, sampler: RssSampler) -> dict:
    sampler.set_phase("B")
    results: dict[int, dict] = {}
    threads = [threading.Thread(target=chaos_session, args=(i, base, minutes, seed, results))
               for i in range(sessions)]
    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=minutes * 60 + 120)
    return results


# --------------------------------------------------------------- phase C ----

def run_phase_c(sampler: RssSampler) -> dict:
    """Shells out to the sibling bare-process script (own env passthrough,
    same BENCHUP_SCENARIO_ENTRIES the caller set) and folds its stdout +
    exit code into this report; `cycle_scenarios.py` remains independently
    runnable (acceptance item 4)."""
    sampler.set_phase("C")
    t0 = time.time()
    proc = subprocess.run([PYTHON, str(CYCLE_SCRIPT)], cwd=str(APP_DIR),
                          capture_output=True, text=True, errors="replace", env=os.environ.copy())
    return {"returncode": proc.returncode, "stdout": proc.stdout, "stderr": proc.stderr,
            "s": round(time.time() - t0, 2)}


# ------------------------------------------------------------------ main ----

def final_health_check(base: str) -> bool:
    """One fresh page load after every phase -- often the FIRST real request
    this server instance ever handled if only phase C ran (that phase never
    touches the running server at all), so a cold Menu.py render (manifest +
    index length read) gets the generous timeout, not the tight one chaos
    actions use."""
    try:
        with sync_playwright() as p:
            browser = p.chromium.launch()
            page = browser.new_page()
            page.goto(base, wait_until="load", timeout=45_000)
            # NOTE: "h1, h2, h3" (tag selector), not `[role="heading"]` -- a
            # native <h1> carries an IMPLICIT accessibility role, no literal
            # role= attribute, so the CSS attribute-selector form matches
            # nothing and always times out (caught live before this fix).
            page.wait_for_selector("h1, h2, h3", timeout=30_000)
            ok = page.get_by_role("heading").count() > 0
            browser.close()
            return ok
    except Exception:  # noqa: BLE001
        return False


def write_report(path: Path, csv_path: Path, cfg: dict, sampler: RssSampler,
                 phase_a_steps, phase_b_results, phase_c_result, server_alive: bool,
                 final_ok: bool) -> tuple[str, bool]:
    phases_run = cfg["phases"]
    stats = {ph: sampler.phase_stats(ph) for ph in phases_run}
    overall_vals = [mb for _, p, mb in sampler.samples if p in phases_run]
    overall_peak = max(overall_vals) if overall_vals else None

    a_fail = sum(1 for s in (phase_a_steps or []) if not s["ok"])
    b_fail = sum(r["n_failures"] for r in (phase_b_results or {}).values())
    b_actions = sum(r["actions"] for r in (phase_b_results or {}).values())
    c_ok = (phase_c_result is None) or (phase_c_result["returncode"] == 0)

    passed = (overall_peak is not None and overall_peak < PEAK_CEILING_MB
             and server_alive and final_ok and c_ok)

    lines = []
    lines.append(f"# Stress report -- {cfg['timestamp']}")
    lines.append("")
    lines.append("## Config")
    lines.append("")
    for k, v in cfg.items():
        lines.append(f"- **{k}**: {v}")
    lines.append("")
    lines.append("## Peak / mean / final RSS per phase (MB, WorkingSetSize)")
    lines.append("")
    lines.append("| phase | n samples | peak | mean | final |")
    lines.append("|---|---|---|---|---|")
    for ph in phases_run:
        s = stats[ph]
        if s["n"] == 0:
            lines.append(f"| {ph} | 0 | - | - | - |")
        else:
            lines.append(f"| {ph} | {s['n']} | {s['peak']:.1f} | {s['mean']:.1f} | {s['final']:.1f} |")
    lines.append(f"| **overall** | {len(overall_vals)} | "
                 f"{overall_peak:.1f} |  |  |" if overall_peak is not None else "| **overall** | 0 | - | | |")
    lines.append("")
    lines.append(f"Ceiling: peak < {PEAK_CEILING_MB:.0f} MB (D11/D12, half the 2.7 GB Community Cloud cap).")
    lines.append("")

    if phase_a_steps is not None:
        lines.append("## Phase A -- deterministic crash-path replay")
        lines.append("")
        lines.append(f"{len(phase_a_steps) - a_fail}/{len(phase_a_steps)} steps ok.")
        lines.append("")
        lines.append("| step | ok | s | error |")
        lines.append("|---|---|---|---|")
        for s in phase_a_steps:
            lines.append(f"| {s['step']} | {s['ok']} | {s['s']} | {s.get('error', '')} |")
        lines.append("")

    if phase_b_results is not None:
        lines.append("## Phase B -- chaos (concurrent sessions)")
        lines.append("")
        lines.append(f"Total actions: {b_actions}. Total failures: {b_fail}.")
        lines.append("")
        lines.append("| session | actions | failures |")
        lines.append("|---|---|---|")
        for sid, r in sorted(phase_b_results.items()):
            lines.append(f"| {sid} | {r['actions']} | {r['n_failures']} |")
        if b_fail:
            lines.append("")
            lines.append("Failure detail (first 20):")
            n = 0
            for sid, r in sorted(phase_b_results.items()):
                for f in r["failures"]:
                    if n >= 20:
                        break
                    lines.append(f"- session {sid}: {f}")
                    n += 1
        lines.append("")

    if phase_c_result is not None:
        lines.append("## Phase C -- bare-process six-scenario cycle")
        lines.append("")
        lines.append(f"`cycle_scenarios.py` exit code: {phase_c_result['returncode']} "
                     f"({phase_c_result['s']}s)")
        lines.append("")
        lines.append("```")
        lines.append(phase_c_result["stdout"].strip())
        lines.append("```")
        lines.append("")

    lines.append("## Server health")
    lines.append("")
    lines.append(f"- server alive throughout (PID never became unreadable): {server_alive}"
                 + (f" (died at t={sampler.died_at:.1f}s)" if sampler.died_at is not None else ""))
    lines.append(f"- final page load after all phases: {'ok' if final_ok else 'FAILED'}")
    lines.append(f"- server stdout/stderr log: `{cfg.get('server_log_name', '')}`")
    lines.append("")
    lines.append(f"## Result: {'PASS' if passed else 'FAIL'}")
    lines.append("")
    lines.append(f"Samples CSV: `{csv_path.name}`")
    lines.append("")

    path.write_text("\n".join(lines), encoding="utf-8")

    with csv_path.open("w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["elapsed_s", "phase", "rss_mb"])
        for t, ph, mb in sampler.samples:
            w.writerow([f"{t:.2f}", ph, f"{mb:.2f}"])

    return ("PASS" if passed else "FAIL"), passed


def main() -> int:
    ap = argparse.ArgumentParser(description="BenchUp V4 memory stress harness (BUILD_PLAN.md D12).")
    ap.add_argument("--minutes", type=float, default=10.0, help="phase B duration per session, minutes")
    ap.add_argument("--sessions", type=int, default=3, help="concurrent chaos sessions (phase B)")
    ap.add_argument("--port", type=int, default=8651)
    ap.add_argument("--seed", type=int, default=1)
    ap.add_argument("--phases", type=str, default="A,B", help="comma list from A,B,C")
    ap.add_argument("--out", type=str, default=str(APP_DIR.parents[0] / "evals" / "stress"))
    args = ap.parse_args()

    phases = [p.strip().upper() for p in args.phases.split(",") if p.strip()]
    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)

    scenario_entries = os.environ.get("BENCHUP_SCENARIO_ENTRIES", "1")
    # BUILD_PLAN.md T1 spec names this exact format (STRESS_<YYYY-MM-DD_HHMM>.md) --
    # minute precision, not seconds. Two runs inside the same minute (only ever
    # happens in rapid manual dev iteration) share a stamp and the later one
    # overwrites the earlier; a real gate run is never that fast.
    stamp = datetime.now().strftime("%Y-%m-%d_%H%M")
    base = f"http://127.0.0.1:{args.port}"

    server_log_path = out_dir / f"STRESS_{stamp}_server.log"
    print(f"[stress] starting server on port {args.port} "
         f"(BENCHUP_SCENARIO_ENTRIES={scenario_entries}) ... log: {server_log_path}")
    server = start_server(args.port, server_log_path)
    server_pid: int | None = None
    sampler: RssSampler | None = None
    phase_a_steps = None
    phase_b_results = None
    phase_c_result = None
    server_alive = False
    final_ok = False

    try:
        if not _wait_for_port(args.port, timeout=90):
            print("FAIL: server did not open its port within 90s")
            return 1
        server_pid = _find_listening_pid(args.port, timeout=30)
        if server_pid is None:
            print("FAIL: could not resolve which PID is LISTENING on the port (netstat)")
            return 1
        rss0 = process_rss_mb(server_pid)
        if rss0 is None:
            print(f"FAIL: could not read RSS for resolved server PID {server_pid}")
            return 1
        same = "same as launched process" if server_pid == server.pid else \
              f"DIFFERENT from launched process pid {server.pid} (Windows child, see module docstring)"
        print(f"[stress] server PID {server_pid} confirmed readable, {rss0[0]:.1f} MB at boot ({same})")

        sampler = RssSampler(server_pid)
        sampler.start()

        if "A" in phases:
            print("[stress] phase A: deterministic crash-path replay ...")
            with sync_playwright() as p:
                browser = p.chromium.launch()
                context = browser.new_context(viewport={"width": 1280, "height": 900}, accept_downloads=True)
                page = context.new_page()
                page.set_default_timeout(60_000)  # cold scenario builds can take a while; 30s default is tight
                phase_a_steps = run_phase_a(page, base, sampler)
                browser.close()
            n_fail = sum(1 for s in phase_a_steps if not s["ok"])
            print(f"[stress] phase A done: {len(phase_a_steps) - n_fail}/{len(phase_a_steps)} steps ok")

        if "B" in phases:
            print(f"[stress] phase B: {args.sessions} sessions x {args.minutes} min chaos ...")
            phase_b_results = run_phase_b(base, args.sessions, args.minutes, args.seed, sampler)
            b_actions = sum(r["actions"] for r in phase_b_results.values())
            b_fail = sum(r["n_failures"] for r in phase_b_results.values())
            print(f"[stress] phase B done: {b_actions} actions, {b_fail} failures")

        if "C" in phases:
            print("[stress] phase C: bare-process six-scenario cycle ...")
            phase_c_result = run_phase_c(sampler)
            print(f"[stress] phase C done: exit {phase_c_result['returncode']}")

        sampler.set_phase("post")
        server_alive = sampler.died_at is None and server.poll() is None
        final_ok = final_health_check(base)
        print(f"[stress] server_alive={server_alive} final_page_ok={final_ok}")

    finally:
        if sampler is not None:
            sampler.stop()
        stop_server(server, server_pid)
        print("[stress] server stopped")

    if sampler is None:
        return 1

    cfg = {
        "timestamp": stamp, "port": args.port, "sessions": args.sessions,
        "minutes_per_session": args.minutes, "seed": args.seed, "phases": phases,
        "scenario_entries_env": scenario_entries, "server_log_name": server_log_path.name,
    }
    report_path = out_dir / f"STRESS_{stamp}.md"
    csv_path = out_dir / f"STRESS_{stamp}_samples.csv"
    result, passed = write_report(report_path, csv_path, cfg, sampler, phase_a_steps,
                                  phase_b_results, phase_c_result, server_alive, final_ok)

    print("\n=== STRESS SUMMARY ===")
    print(f"config: sessions={args.sessions} minutes={args.minutes} seed={args.seed} "
         f"scenario_entries={scenario_entries} port={args.port} phases={phases}")
    for ph in phases:
        s = sampler.phase_stats(ph)
        if s["n"]:
            print(f"phase {ph}: peak={s['peak']:.1f} MB mean={s['mean']:.1f} MB "
                 f"final={s['final']:.1f} MB n={s['n']}")
        else:
            print(f"phase {ph}: no samples")
    overall_vals = [mb for _, p, mb in sampler.samples if p in phases]
    if overall_vals:
        print(f"overall peak: {max(overall_vals):.1f} MB (ceiling {PEAK_CEILING_MB:.0f} MB)")
    print(f"server_alive={server_alive} final_page_ok={final_ok}")
    print(f"RESULT: {result}")
    print(f"report: {report_path}")
    print(f"csv: {csv_path}")

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
