# Playwright UI suite (`tests/ui/smoke.py`, `tests/ui/probe.py`, `tests/ui/switchback.py`)

Three end-to-end checks against a live `streamlit run Menu.py` server, all headless Chromium
through Playwright (installed with `requirements-dev.txt`).

- `smoke.py --port 8611` starts its own server and walks the three pages as a reader would:
  Menu cards; Find (search, the eight profile tiles, both taxonomy and counting toggles across
  all six combinations, the topic-planes panel, the 15-sheet workbook); Compare (deep link
  `?compare=A,B`, named slots, Clear, seeding from Find, Profile/Impact tabs, the topic-overlap
  selector/plane/balance bars, the 6-sheet workbook, the share box); Methods (eleven sections,
  the note download). Every page is measured at 1920, 1280 and 390 px for
  `scrollWidth <= innerWidth`. One pass/fail line per check and a summary count; non-zero exit
  on any failure.
- `probe.py all` (or `find`, `compare`, `methods`, `menu`) recomputes rendered values straight
  from the data layer (`lib/compare_data.py`, `lib/collab_data.py`, `lib/leaders_data.py`) and
  compares them with what the page shows, one fresh server per page.
- `switchback.py --port 8680 --runs 3` (view-persistence acceptance): opens Find, sets the topic-planes
  selector/slider, records a hash of both plane figures plus the value of every persisted
  control checked, navigates to Compare via a REAL sidebar nav-link click (never `page.goto`
  between pages under a persistence claim -- see its own module docstring and `_click_nav`
  below), then back to Find -- asserting the controls and figure hashes are unchanged and that
  both the page-switch time and the re-expanded-panel time are `<= 1.5 s`. Repeats 3x in one
  server session and prints a small table; non-zero exit on any failure.

All three scripts always kill the server they started (`finally` block). Streamlit's true scroll
container is `section.stMain`, not the document body: full-page captures resize the viewport to
its `scrollHeight` first, or they come out one viewport tall.

DOM idioms `switchback.py` adds (live-verified against this build, not guessed): a segmented
control's selected option is `button[aria-checked='true']` inside its own `.st-key-<key>`
element (`data-variant="segmented_control"` on every option button); a slider's value is its
(accessibly hidden but keyboard-focusable) `input[type=range]`'s own `value` attribute, steppable
by `step` with `ArrowLeft`/`ArrowRight` once clicked/focused; a radio's selected option is
`label[data-selected='true']`; `st.selectbox` on this build renders as a react-aria combobox --
`[data-baseweb='select']` (`smoke.py`'s own `_open_select` primary selector) matches NOTHING for
any selectbox on this build, live-confirmed on `tree` too, not only Compare's slots -- `_open_
select` still works today only because its own fallback (`loc.count()==0` -> click the whole
`.st-key-<key>` container, which lands on the input and opens the dropdown regardless) is the
path that always fires; `switchback.py` instead opens the dropdown directly with `page.get_by_
role("combobox", name=<label>)`, the same idiom `tests/stress/run_stress.py`'s own `set_
combobox`/`resolve_picker_if_present` already use for exactly this widget.
