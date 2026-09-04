# Memory stress harness

Permanent gate for the RAM fit the app's architecture exists to buy: Streamlit Community
Cloud hard-caps a deployed app's container at **2.7 GB**. The engine keeps
exactly ONE (taxonomy, counting-basis) scenario substrate dict resident at a time
(`lib/engine/scenario_cache.py`, `max_entries=1`); this harness is the thing that
actually proves that holds up under real, sustained, concurrent use — not just a
bare-process cycle.

## What it measures, and against what

| phase | what it drives | how |
|---|---|---|
| **A** | the measured crash path: open an institution, cycle basis and taxonomy, visit Compare, come back, download a workbook | one continuous Playwright browser context, deterministic script, waits for Streamlit's own "running" indicator to clear between steps |
| **B** | sustained concurrent multi-user load | N browser contexts (`--sessions`, default 3) in parallel threads, each running a seeded-random action loop for `--minutes` (default 10) with only fixed 300–1500 ms pauses — **no waiting for spinners**, so it genuinely outruns what a careful user would do |
| **C** | the engine in isolation, no browser/server at all | `cycle_scenarios.py`: one bare Python process calls `scenario_cache.bundle()` then `get()` for all six (tree, basis) scenarios in sequence |

Phase B's own action set (`CHAOS_ACTIONS`, one picked at random per loop iteration):
`find_seed`, `scenario_combo`, `compare_pair`, `methods`, `download`, `scroll`, plus two that
exercise the bounded per-pair/per-institution topic-plane caches: `find_topic_controls`
(open/reuse Find, expand the topic-planes panel, change the "Topics shown" selector / slider /
FWCI-mean-median radio) and `compare_overlap_controls` (open/reuse Compare, change the SAME
three controls on the topic-overlap section). Neither waits for the resulting rerun to settle,
matching this phase's own "no waiting for spinners" rule.

Every 0.5 s, a background thread samples the **Streamlit server's own python.exe**
`WorkingSetSize` (via `ops/rss_probe.py`, stdlib ctypes — never the Playwright/
Chromium client process) — the same method an earlier stress harness
established. Samples are tagged with the phase running at that moment.

**Pass line:** peak RSS across every measured phase `< 1,800 MB` (half the 2.7 GB
cap — the same ceiling `tests/test_ram_budget.py::test_scenario_cycle` uses
for its own, narrower, bare-process budget) **and** the server never dies (its PID
stays openable throughout, and one final page load after everything succeeds).

**Known finding:** at the full
acceptance duration (`--minutes 8`, 3 sessions) the app currently **FAILS** this
gate — peak 2,511 MB, driven by a late-window burst of concurrent `/Compare`
requests for many distinct institution pairs (Compare's own page-level
`st.cache_data` caches, not the scenario cache the engine redesign targets:
Compare is pinned to one scenario throughout). Shorter runs (4 min) pass
comfortably and reproducibly (~1,600 MB peak, two independent runs agree within
2%) — the failure is duration/concurrency-dependent. This is the gate correctly
finding a real issue, not a harness defect; the fix is page-level cache bounds
elsewhere in the app.

## Running it

```bash
cd V4/app
..\envs\env-app\Scripts\python.exe tests/stress/run_stress.py --minutes 10 --sessions 3 --phases A,B,C
```

Args (`run_stress.py`):

| flag | default | meaning |
|---|---|---|
| `--minutes` | 10 | phase B duration, per session |
| `--sessions` | 3 | concurrent phase-B browser contexts |
| `--port` | 8651 | server port (pick a free one if running alongside another instance) |
| `--seed` | 1 | phase-B RNG seed, per-session offset `seed*1000 + session_id` — reproducible chaos |
| `--phases` | `A,B` | comma list from `A,B,C` — C is a separate bare process shelled out to `cycle_scenarios.py` |
| `--out` | `tests/stress/reports/` | report + CSV destination |

A single command times out at 10 minutes in some harnesses — keep `--minutes ≤ 8`
per invocation, or run it as a background process and poll. A full gate run uses
`--minutes 10`.

Phase C alone, standalone (no server, seconds not minutes):

```bash
..\envs\env-app\Scripts\python.exe tests/stress/cycle_scenarios.py
```

## Reading the report

`tests/stress/reports/STRESS_<YYYY-MM-DD_HHMM>.md` + a sibling `..._samples.csv` (every
0.5 s sample: `elapsed_s, phase, rss_mb`). The report has:
- **Config** — exact args, and `BENCHUP_SCENARIO_ENTRIES` read from the environment
  the harness itself ran under (see "Broken control" below).
- **Peak / mean / final RSS per phase**, plus an overall peak across every phase
  that ran, against the 1,800 MB ceiling.
- **Phase A** — each of the 11 replay steps, ok/fail, seconds.
- **Phase B** — total actions and failures per session, plus the first 20 failure
  messages if any occurred.
- **Phase C** — `cycle_scenarios.py`'s own stdout table folded in verbatim.
- **Server health** — whether the PID stayed openable the whole run, and whether
  one final page load after everything succeeded.
- **Result: PASS/FAIL.** `run_stress.py` exits 0 iff PASS.

## Broken control (why you should trust the PASS)

A harness that always reports a low peak regardless of what the app does is not
proving anything. `lib/engine/scenario_cache.py` reads its resident-scenario cap
from `BENCHUP_SCENARIO_ENTRIES` (default `1`) precisely so this harness can force
the OLD (pre-fix) behaviour — three scenarios resident at once, the actual
Community-Cloud crash condition — without touching any app code:

```bash
# control (fix in effect)
..\envs\env-app\Scripts\python.exe tests/stress/run_stress.py --phases A,B --minutes 4 --port 8651

# broken control (pre-fix behaviour reproduced)
set BENCHUP_SCENARIO_ENTRIES=3
..\envs\env-app\Scripts\python.exe tests/stress/run_stress.py --phases A,B --minutes 4 --port 8652
```

`run_stress.py` passes `env=os.environ.copy()` (not a fresh environment) to the
spawned server, so whatever `BENCHUP_SCENARIO_ENTRIES` is set to in the CALLING
shell reaches it unchanged — this is the whole mechanism, no code path here treats
the two runs differently.

**Measured:**

| | entries=1 | entries=3 |
|---|---|---|
| phase C (bare, visits each of the 6 scenarios once) | 1064.8 MB, eviction proof OK | **1288.8 MB** (+224 MB), eviction proof **FAILED** |
| phase A (one deterministic session) | 1257–1283 MB | **1306.7 MB** (higher) |
| phase B (3-session chaos, 4 min) | 1591–1624 MB (two runs, ±2%) | 1302.4 MB (**lower**) |

Phase C is the decisive proof: a bare process visiting all 6 (tree, basis)
combinations exactly once, no repeats, no browser/network noise — under
`entries=3` the cache genuinely stops evicting (the weakref proof fails on every
swap), so RSS keeps climbing instead of plateauing. Phase A corroborates in the
same direction. **Phase B goes the other way, reproducibly (not noise — two
`entries=1` runs agree within 2%)**: chaos repeatedly re-picks among only 6
possible combos, so a higher `entries` cap raises the cache HIT rate, which
*avoids* the transient double-allocation moment (old scenario's arrays still
live while the new one builds) that dominates the PEAK reading under
`entries=1`'s constant forced eviction+rebuild churn. This is a genuine,
explainable property of chaos over a small bounded state space, not a harness
gap — checked for a fixable coverage issue first (phase B already spends ~1/6 of
its actions on scenario switches), fixing the harness before doubting the app;
none was found. **Trust phase C (and phase A)
for this specific claim; don't expect phase B's peak to move the same direction.**

## A Windows gotcha this harness works around

`subprocess.Popen([python, "-m", "streamlit", "run", ...])`'s own `proc.pid` is
**not reliably the real server** on this box: Streamlit's bootstrap spawns a
separate CHILD python.exe that does the actual serving, while the launched process
stays a ~5 MB wrapper for its whole life (confirmed with `Get-CimInstance
Win32_Process -Filter "ParentProcessId=<pid>"` — the child even resolves a
DIFFERENT `python.exe` off PATH than `sys.executable`). Sampling `proc.pid` directly
does not fail loudly — it reads a flat, tiny, healthy-looking number for the whole
run, a **silent false PASS**. `run_stress.py` resolves the real PID by asking
`netstat -ano` which process is `LISTENING` on the server's port, and terminates
**both** PIDs (the launched one and the resolved one, if different) so nothing is
ever left orphaned. See the module docstring / `_find_listening_pid` for detail.

## Selector choices (role/text, not test ids)

This harness owns no page file, so every interaction goes through Playwright role or
label locators confirmed live against the running app (not guessed from source):

- Nav: `get_by_role("link", name="Open Find peers")` / `"Open Compare"` / `"Open How
  it is built"` (Menu.py's page cards; the label text is `copy.NAV[...]`, read live).
- Search box: `get_by_label("Institution name, acronym or alternative name")`
  (`lib/copy.py FIND["SEED_SEARCH_LABEL"]`); auto-selects on a single exact-name hit
  (`lib/search.py`), else a `get_by_role("combobox", name="Institution to profile")`
  picker appears.
- Sidebar scenario controls: `get_by_role("combobox", name="Subject taxonomy")` /
  `"Counting basis")` — Streamlit's selectbox renders as a BaseWeb combobox
  (`role="combobox"`), NOT a `<select>`; click it, then click the option by
  `get_by_role("option", name=<label text>)` from `copy.TREE_LABELS` /
  `copy.BASIS_LABELS`.
- Downloads: Find's button reads **"Download this profile and benchmark (Excel)"**;
  Compare's reads **"Download this view (Excel)"** — two different strings, read
  live off the running app (`lib/copy.py`'s own `EXPORT_XLSX_BUTTON` constants do
  NOT match what Compare renders; `views_compare.py` reads a different key).
  Workbook generation can take 20–40 s on a cold scenario — `expect_download` uses a
  45 s timeout, not Playwright's 30 s default.
- Scroll container: `[data-testid="stMain"]` — `document.body.scrollHeight` is 0 in
  this Streamlit version (the real scrollable element is `stMain`, not `body`).
- Error detection: `get_by_text("Oh no", exact=False)` — Streamlit's own uncaught-
  exception box title. A websocket disconnect has no equally reliable DOM signal;
  any Playwright exception raised mid-action is counted as a phase-B failure too.
- Compare deep link: `?compare=A,B` (`lib/selection.py::deeplink`) — used directly
  via `page.goto`, never by typing into the slot search boxes (the spec here is:
  "never type into the slot widgets, whose labels may still change").

If any of these break on a future page edit, re-probe the running app rather than
guessing from source — `probe_selectors.py`-style throwaway scripts (not checked
in) are how the ones above were confirmed.

## Seeds

The same 12 institutions the reference goldens already vetted
for type/size variety — this harness never re-derives its own sample:

```
I154202486   Ifremer (government)
I4210107283  Royal Netherlands Institute for Sea Research (facility)
I35440088    ETH Zurich (education)
I1294671590  Centre National de la Recherche Scientifique (government)
I68947357    Université de Strasbourg (education)
I4210143826  Institut National des Sciences Appliquées Centre Val de Loire (education)
I142910587   University of Salento (education)
I4210086484  HIA du Val-de-Grâce à Paris (healthcare)
I4210149564  Ospedale SS. Annunziata (healthcare)
I4210150693  The Medical Device (United Kingdom) (company)
I4210131494  Ministère de l'Enseignement Supérieur, de la Recherche et de l'Espace (government)
I4210142177  Pfizer-University of Granada-Junta de Andalucía Centre for Genomics and
             Oncological Research (facility)
```

## Files in this folder

- `run_stress.py` — phases A + B, server lifecycle, report + CSV writer.
- `cycle_scenarios.py` — phase C, standalone, no server.
- This file.

Reports and samples live in `tests/stress/reports/` (gitignored -- local,
regenerable output, never committed).
