# Playwright UI suite (`tests/ui/smoke.py`, `tests/ui/probe.py`)

Two end-to-end checks against a live `streamlit run Menu.py` server, both headless Chromium
through Playwright (installed with `requirements-dev.txt`).

- `smoke.py --port 8611` starts its own server and walks the three pages as a reader would:
  Menu cards; Find (search, the eight profile tiles, both taxonomy and counting toggles across
  all six combinations, the 14-sheet workbook); Compare (deep link `?compare=A,B`, named slots,
  Clear, seeding from Find, Profile/Impact tabs, the shared-frontier mirror chart's OpenAlex
  links, Show all, the 7-sheet workbook before and after Show all, the share box); Methods
  (eleven sections, the note download). Every page is measured at 1920, 1280 and 390 px for
  `scrollWidth <= innerWidth`. One pass/fail line per check and a summary count; non-zero exit
  on any failure.
- `probe.py all` (or `find`, `compare`, `methods`, `menu`) recomputes rendered values straight
  from the data layer (`lib/compare_data.py`, `lib/collab_data.py`, `lib/leaders_data.py`) and
  compares them with what the page shows, one fresh server per page.

Both scripts always kill the server they started (`finally` block). Streamlit's true scroll
container is `section.stMain`, not the document body: full-page captures resize the viewport to
its `scrollHeight` first, or they come out one viewport tall.
