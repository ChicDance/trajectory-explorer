"""Trajectory Explorer — interactive demo for drone/camera trajectory
datasets (DLR-UT to start), with SMoS-style safety metrics (TTC/DRAC).

Thin orchestration layer: sidebar controls + session state live here, all
data loading goes through `data/`, all metric computation through
`analysis/`, all rendering through `viz/`.
"""

import time

import pandas as pd
import streamlit as st

from trajectory_explorer.analysis import aggregates, interaction, kinematics, risk
from trajectory_explorer.data.loader import load_classification, load_dataset
from trajectory_explorer.data.registry import get_dataset
from trajectory_explorer.viz import charts, scene_map
from trajectory_explorer.viz.colors import CLASS_ORDER

DATASET_KEY = "dlr_ut_session_01"
PLAYBACK_STEP_S = 0.5
PLAYBACK_TICK_S = 0.15


@st.cache_data(show_spinner=False)
def compute_stats(key: str, visible_classes: tuple[str, ...]) -> dict:
    """Dataset-wide stats-tab views. Independent of `current_time`, so this
    is cached per (dataset, filter) rather than rebuilt on every rerun --
    including every ~150ms playback tick, which previously rebuilt these
    unconditionally since Streamlit executes every tab's code on every
    rerun regardless of which tab is visible.
    """
    dataset = load_dataset(key)
    classification = load_classification(key)
    classes = list(visible_classes) if visible_classes else None
    stats_dataset = dataset.get_by_object_class(classes) if classes else dataset
    return {
        "speed": aggregates.speed_distribution(stats_dataset, classification),
        "acceleration": aggregates.acceleration_distribution(stats_dataset, classification),
        "flow": aggregates.traffic_flow_over_time(dataset, bin_seconds=15),
    }


@st.cache_data(show_spinner=False)
def get_export_csv_bytes(key: str, visible_classes: tuple[str, ...]) -> bytes:
    """Filtered-trajectory CSV for the sidebar download button.

    Independent of `current_time` (like `compute_stats`), but this one was
    the single biggest per-rerun cost in the app: `get_by_object_class`
    (~1.1s) + `to_csv` on ~9MB of rows (~1.5s) -- previously recomputed on
    every rerun since a `download_button`'s `data=` argument is evaluated
    eagerly every script run, including every ~150ms playback tick.
    """
    dataset = load_dataset(key)
    classes = list(visible_classes) if visible_classes else None
    filtered = dataset.get_by_object_class(classes) if classes else dataset
    return _flatten_for_export(filtered).to_csv(index=False).encode("utf-8")


@st.cache_resource(show_spinner=False)
def get_heatmap_deck(key: str):
    """Static spatial-density deck (whole session, all classes) -- same
    caching rationale as `compute_stats`.
    """
    info = get_dataset(key)
    dataset = load_dataset(key)
    return scene_map.build_heatmap_deck(
        dataset, info.crs,
        orthophoto_path=info.orthophoto_path,
        orthophoto_bbox=info.orthophoto_bbox,
    )


def _flatten_for_export(dataset) -> pd.DataFrame:
    """Flatten a TASI hierarchical-column dataset into a plain CSV-able frame."""
    # `reset_index()` on a tasi CollectionBase subclass returns the same
    # subclass (not a plain DataFrame), which overrides `.to_csv()` with an
    # incompatible signature -- force a plain pandas DataFrame first.
    df = pd.DataFrame(dataset).reset_index()
    df.columns = [
        "_".join(part for part in col if part) if isinstance(col, tuple) else col
        for col in df.columns
    ]
    return df


def compute_interactions_with_progress(dataset) -> pd.DataFrame:
    """Run the ~5-10s pairwise TTC/DRAC pass with a visible progress bar.

    Only used for safety-tab features (near-misses, Conflict Explorer, live
    risk coloring, safety report) -- deliberately NOT run automatically on
    every dataset load, since most of the app doesn't need it.
    """
    bar = st.progress(0.0, text="Computing pairwise TTC/DRAC...")

    def _on_progress(done: int, total: int) -> None:
        frac = done / total if total else 1.0
        bar.progress(frac, text=f"Computing pairwise TTC/DRAC... {done}/{total} frames")

    result = interaction.pairwise_interactions(dataset, progress_callback=_on_progress)
    bar.empty()
    return result


def build_safety_report(
    info, dataset, class_by_id: pd.Series,
    interactions: pd.DataFrame, ranking: pd.DataFrame, n_near_miss: int,
) -> str:
    n_tracks = int(dataset.index.get_level_values("id").nunique())
    duration_s = (
        dataset.index.get_level_values("timestamp").max()
        - dataset.index.get_level_values("timestamp").min()
    ).total_seconds()
    speed_by_class = aggregates.speed_distribution(dataset, class_by_id).groupby("classification")["speed"]

    lines = [
        f"# Safety Report — {info.name}",
        "",
        f"Source: {info.source_url} · License: {info.license_name} ({info.license_url})",
        "",
        f"- Session duration: {duration_s:.0f} s",
        f"- Tracks: {n_tracks}",
        f"- Near-misses (min TTC < 1.5 s): **{n_near_miss}**",
        "",
        "## Speed by class (mean / max, m/s)",
        "",
    ]
    for cls, group in speed_by_class:
        lines.append(f"- {cls}: mean {group.mean():.1f}, max {group.max():.1f}")

    lines += ["", "## Top-5 most severe conflicts", ""]
    if ranking.empty:
        lines.append("No conflicts detected within the tracked distance threshold.")
    else:
        lines.append("| id_a | id_b | min TTC (s) | max DRAC (m/s²) | timestamp |")
        lines.append("|---|---|---|---|---|")
        for _, row in ranking.head(5).iterrows():
            lines.append(
                f"| {row['id_a']} | {row['id_b']} | {row['min_ttc_s']:.2f} | "
                f"{row['max_drac_mps2']:.2f} | {row['worst_timestamp']} |"
            )

    lines += [
        "",
        "---",
        "Generated by Trajectory Explorer. TTC/DRAC use a simplified "
        "straight-line, constant-velocity model (not heading/bounding-box aware).",
    ]
    return "\n".join(lines)


def main() -> None:
    st.set_page_config(page_title="Trajectory Explorer", layout="wide")

    info = get_dataset(DATASET_KEY)
    dataset = load_dataset(DATASET_KEY)
    class_by_id = load_classification(DATASET_KEY)

    timestamps = dataset.index.get_level_values("timestamp").unique().sort_values()
    t_min, t_max = timestamps.min(), timestamps.max()
    total_seconds = (t_max - t_min).total_seconds()

    if "time_offset" not in st.session_state:
        st.session_state.time_offset = 0.0
    if "playing" not in st.session_state:
        st.session_state.playing = False

    # --- Sidebar -----------------------------------------------------------
    st.sidebar.title("Trajectory Explorer")
    st.sidebar.markdown(f"**{info.name}**")
    st.sidebar.caption(info.description)
    st.sidebar.markdown(
        f"License: [{info.license_name}]({info.license_url}) · "
        f"[Source]({info.source_url})"
    )
    if info.orthophoto_attribution:
        st.sidebar.caption(info.orthophoto_attribution)
    st.sidebar.divider()

    visible_classes = st.sidebar.multiselect(
        "Object classes", CLASS_ORDER, default=CLASS_ORDER
    )

    st.sidebar.divider()
    st.sidebar.caption("Safety metrics (TTC/DRAC)")
    if "interactions" not in st.session_state:
        st.sidebar.caption(
            "Near-misses, Conflict Explorer, live risk coloring and the "
            "safety report all need a one-time pass over the session "
            "(~5-10s) that isn't run automatically."
        )
        if st.sidebar.button("Compute safety metrics", use_container_width=True):
            st.session_state.interactions = compute_interactions_with_progress(dataset)
            st.rerun()
        show_risk = False
    else:
        st.sidebar.success("Safety metrics computed.", icon="✅")
        show_risk = st.sidebar.checkbox(
            "Color by live risk (TTC)", value=False,
            help="Colors current object positions by their live collision risk "
                 "(green/amber/red) instead of by object class.",
        )

    st.sidebar.divider()
    st.sidebar.caption("Export")
    st.sidebar.download_button(
        "Filtered trajectories (CSV)",
        data=get_export_csv_bytes(DATASET_KEY, tuple(visible_classes)),
        file_name="trajectories_filtered.csv",
        mime="text/csv",
        use_container_width=True,
    )

    # --- Playback controls ---------------------------------------------------
    ctrl_cols = st.columns([1, 1, 6])
    if ctrl_cols[0].button("Play", use_container_width=True, disabled=st.session_state.playing):
        st.session_state.playing = True
    if ctrl_cols[1].button("Pause", use_container_width=True, disabled=not st.session_state.playing):
        st.session_state.playing = False

    if st.session_state.playing:
        st.session_state.time_offset = min(
            st.session_state.time_offset + PLAYBACK_STEP_S, total_seconds
        )
        if st.session_state.time_offset >= total_seconds:
            st.session_state.playing = False

    if "pending_time_offset" in st.session_state:
        st.session_state.time_offset = st.session_state.pop("pending_time_offset")

    offset = st.slider(
        "Playback time (s into session)",
        min_value=0.0,
        max_value=float(total_seconds),
        step=0.25,
        key="time_offset",
        label_visibility="collapsed",
    )
    current_time = t_min + pd.Timedelta(seconds=offset)
    st.caption(f"t = {current_time.strftime('%H:%M:%S.%f')[:-4]} (+{offset:.2f}s)")

    interactions = st.session_state.get("interactions")
    have_interactions = interactions is not None
    ranking = interaction.conflict_ranking(interactions, top_n=20) if have_interactions else None
    n_near_miss = interaction.near_miss_count(interactions) if have_interactions else None

    risk_by_track = (
        risk.current_risk_by_track(interactions, current_time)
        if (show_risk and have_interactions)
        else None
    )

    # --- Tabs ----------------------------------------------------------------
    tab_scene, tab_object, tab_stats = st.tabs(
        ["Scene", "Object Detail", "Statistics & Safety"]
    )

    with tab_scene:
        map_col, conflict_col = st.columns([3, 1])
        with map_col:
            deck = scene_map.build_scene_deck(
                dataset,
                info.crs,
                current_time,
                class_by_id,
                visible_classes=visible_classes or None,
                risk_by_track=risk_by_track,
                orthophoto_path=info.orthophoto_path,
                orthophoto_bbox=info.orthophoto_bbox,
            )
            st.pydeck_chart(deck, use_container_width=True)
        with conflict_col:
            if not have_interactions:
                st.caption(
                    "Near-misses and the Conflict Explorer need the safety "
                    "metrics pass — use the button in the sidebar."
                )
            else:
                st.metric("Near-misses (TTC < 1.5s)", n_near_miss)
                st.caption("Conflict Explorer — click to jump")
                for _, row in ranking.head(8).iterrows():
                    label = f"#{int(row['id_a'])}↔#{int(row['id_b'])} · TTC {row['min_ttc_s']:.1f}s"
                    if st.button(label, key=f"jump_{row['id_a']}_{row['id_b']}", use_container_width=True):
                        jump_offset = (row["worst_timestamp"] - t_min).total_seconds()
                        # Can't assign to st.session_state.time_offset here --
                        # the `time_offset`-keyed slider widget below has
                        # already been instantiated earlier in this same run,
                        # and Streamlit raises StreamlitWidgetAlreadyInstantiatedError
                        # for that. Stash it and apply before the slider is
                        # (re-)created on the rerun this triggers instead.
                        st.session_state.pending_time_offset = max(0.0, min(jump_offset, total_seconds))
                        st.session_state.playing = False
                        st.rerun()

    # Streamlit executes every tab's body on every rerun regardless of which
    # tab is visible (tabs are CSS-hidden, not skipped) -- these two tabs'
    # content doesn't depend on `current_time`, so rebuilding and
    # re-serializing them on every ~150ms playback tick was pure waste and
    # the dominant remaining cost keeping the Scene tab's animation from
    # running near real-time. Skip them while playing; they still reflect
    # the current filter/safety-metrics state as soon as playback is paused.
    playing = st.session_state.playing

    with tab_object:
        if playing:
            st.caption("Paused during playback for smooth animation — pause to view.")
        else:
            track_ids = sorted(int(i) for i in dataset.ids)
            selected_track = st.selectbox("Track", track_ids)
            ts_df = kinematics.object_timeseries(dataset, selected_track)
            st.plotly_chart(charts.kinematics_chart(ts_df), use_container_width=True)

    with tab_stats:
        if playing:
            st.caption("Paused during playback for smooth animation — pause to view.")
        else:
            stats = compute_stats(DATASET_KEY, tuple(visible_classes))

            col_a, col_b = st.columns(2)
            col_a.plotly_chart(
                charts.speed_distribution_chart(stats["speed"]),
                use_container_width=True,
            )
            col_b.plotly_chart(
                charts.acceleration_distribution_chart(stats["acceleration"]),
                use_container_width=True,
            )

            st.plotly_chart(
                charts.traffic_flow_chart(stats["flow"]),
                use_container_width=True,
            )

            st.subheader("Spatial density")
            st.pydeck_chart(get_heatmap_deck(DATASET_KEY), use_container_width=True)

            st.subheader("Safety report")
            if not have_interactions:
                st.info(
                    "Compute safety metrics (sidebar button) to see near-misses, "
                    "the conflict ranking and a downloadable safety report."
                )
            else:
                report_md = build_safety_report(
                    info, dataset, class_by_id, interactions, ranking, n_near_miss
                )
                rep_col, csv_col = st.columns(2)
                rep_col.download_button(
                    "Download safety report (Markdown)",
                    data=report_md.encode("utf-8"),
                    file_name="safety_report.md",
                    mime="text/markdown",
                    use_container_width=True,
                )
                csv_col.download_button(
                    "Download conflict ranking (CSV)",
                    data=ranking.to_csv(index=False).encode("utf-8"),
                    file_name="conflict_ranking.csv",
                    mime="text/csv",
                    use_container_width=True,
                )
                st.dataframe(ranking, use_container_width=True, hide_index=True)

    if st.session_state.playing:
        time.sleep(PLAYBACK_TICK_S)
        st.rerun()


if __name__ == "__main__":
    main()
