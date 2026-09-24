# CLAUDE.md

Working notes for Claude Code (or anyone else) picking this repo back up.
`PLAN.md` is the original one-shot build plan (partly outdated -- e.g. it
assumed `tasi` ships TTC/DRAC, and predates the src-layout move); this file
is the living reference instead.

## Running it

```bash
uv sync

# fetch the DLR-UT trajectory data (see "Never commit the dataset" below)
uv run python scripts/download_dlr_ut.py
uv run python scripts/fetch_sample_data.py

uv run streamlit run app.py
```

Root `app.py` is a thin wrapper (`from trajectory_explorer.app import main; main()`)
so the run command stays simple. The real code is `src/trajectory_explorer/`
(src layout, installable via hatchling -- see `pyproject.toml`).

## Layout

```
src/trajectory_explorer/
  app.py         # Streamlit orchestration: sidebar, playback, tabs
  data/          # Dataset registry, cached loading, CRS conversion
  analysis/      # Kinematics, aggregate stats, TTC/DRAC, risk levels
  viz/           # pydeck scene/heatmap builders, Plotly charts, colors
scripts/         # One-off fetch scripts, run manually, not part of the package
sample_data/     # Aerial photo (bundled); trajectory CSV lands here once fetched
```

## Never commit the DLR-UT dataset

`sample_data/dlr_ut/*.csv` is gitignored on purpose. It's a third-party
licensed dataset (CC BY 4.0, DLR's) -- this repo redistributes code, not the
data. Users fetch it themselves via the two scripts above (which pull it
from Zenodo through `tasi`). The aerial orthophoto (`orthophoto.jpeg`) is
fine to commit -- it's our own small (~130KB) asset from a separate source
(LGLN Niedersachsen), fetched once via `scripts/fetch_orthophoto.py`.

If a future change accidentally re-adds a data CSV to a commit, remove it
with a normal follow-up commit -- do not amend/force-push to scrub it unless
it's still the *only* commit in the repo (that was a one-time move early on;
see git history discussion below).

## Git workflow

Normal additive commits from here on, no amending/force-pushing. (Early in
this project's life there was exactly one commit and it accidentally
contained the trajectory CSV; that was fixed by amending *that single
commit* and force-pushing, before anyone else could have depended on it.
That was a one-time exception, not the pattern to repeat.)

## Non-obvious gotchas (found the hard way)

**pydeck / deck.gl (this bundled version) has three sharp edges:**
1. Passing a plain Python string as a `pdk.Layer(...)` kwarg gets
   auto-wrapped as a live `"@@=<value>"` accessor expression (meant for
   column-reference accessors like `get_path="path"`). This silently breaks
   literal values -- e.g. `width_units="meters"` becomes a lookup for a
   nonexistent `"meters"` column. Fix: omit the kwarg if the default already
   matches (deck.gl defaults `widthUnits`/`radiusUnits` to meters anyway),
   or use `pydeck.types.String(value, quote_type="")` for a literal you
   can't omit.
2. `PolygonLayer(..., stroked=True, get_line_color=[...])` renders every
   polygon as a tiny mispositioned sliver instead of the intended filled
   shape, in this pydeck/deck.gl bundle. `filled=True, stroked=False` (no
   outline) works correctly. Found via minimal `to_html()` repros -- don't
   re-debug this from scratch, just don't use `stroked=True` here.
3. `pydeck.types.Image(path)` derives the embedded data-URI MIME type from
   the file's literal suffix (`.jpg` -> `"image/jpg"`, not a real IANA MIME
   type) -- deck.gl's loader then rejects it ("No valid loader found"). The
   orthophoto asset is named `.jpeg` specifically so this produces the
   valid `"image/jpeg"`; keep that extension if you ever replace the file.

**Streamlit reruns execute every tab's body, every time**, regardless of
which tab is visible (tabs are CSS-hidden, not skipped). Combined with the
playback loop's `st.rerun()` every ~150ms, anything expensive built inside a
tab gets rebuilt on every tick even while paused on a different tab. Two
concrete fixes already applied because of this:
- `dataset.most_likely_class(...)` costs ~1s and was called 4x per rerun;
  it's now computed once via `data/loader.py:load_classification` (cached)
  and threaded through as a parameter instead of recomputed.
- The Statistics & Safety and Object Detail tabs' bodies are skipped
  entirely while `st.session_state.playing` is True (see `app.py`) -- they
  don't depend on `current_time` anyway, so there's nothing lost by not
  rebuilding them every tick.
- The sidebar CSV export used to rebuild+encode the full dataset
  (~2.6s: `get_by_object_class` + `to_csv`) on every single rerun because a
  `download_button`'s `data=` is evaluated eagerly every script run. It's
  now cached by `(dataset_key, visible_classes)` in
  `app.py:get_export_csv_bytes`.

**Don't assign to `st.session_state.<key>` for a widget after that widget
has already been instantiated earlier in the same script run** -- e.g. a
button below a `st.slider(..., key="time_offset")` cannot do
`st.session_state.time_offset = ...` and then `st.rerun()`; Streamlit raises
`StreamlitWidgetAlreadyInstantiatedError`. Pattern used instead: stash the
target value under a different key (`pending_time_offset`), and apply it to
the real key *before* the slider is (re-)created on the next run (see the
Conflict Explorer jump buttons in `app.py`).

**CRS**: DLR-UT trajectory positions are in EPSG:32632 (UTM 32N) --
verified empirically against known Braunschweig coordinates, *not* the
tmerc CRS declared in the bundled OpenDRIVE `.xodr`'s `geoReference` header
(that describes the road file's own separate local frame). The `yaw` column
is standard math heading in degrees (measured from east, counter-clockwise
positive) -- verified against `atan2(velocity.northing, velocity.easting)`.

**`tasi` 0.15.4 does not ship TTC/DRAC**, only `tasi.smos.pet.PET`
(Post-Encroachment Time). TTC/DRAC are implemented from scratch in
`analysis/interaction.py` using a simplified straight-line,
constant-velocity model.

## Background process management (when developing with an agent)

Always start `streamlit run` with the harness's actual background-task
mechanism, not shell `&` backgrounding inside a single tool call -- the
process dies when that call's shell session ends. Before restarting on a
port, check what's actually listening (`Get-NetTCPConnection -LocalPort
<port> -State Listen`) rather than guessing, so you don't kill an unrelated
process.
