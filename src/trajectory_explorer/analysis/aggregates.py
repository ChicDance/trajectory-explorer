"""Dataset-wide aggregate views used by the statistics/overview pages.

All functions take a `tasi.dlr.DLRTrajectoryDataset` (or a filtered
sub-dataset, e.g. `dataset.cars`) and return plain pandas DataFrames with a
fixed, documented column contract so the `viz` layer can build charts
without knowing about TASI's hierarchical-column schema.
"""

from __future__ import annotations

import numpy as np
import pandas as pd

# Above this many pose-rows, heatmap_points subsamples for rendering
# performance -- both pydeck's client-side heatmap aggregation and the
# JSON payload size (each extra 10k rows costs real seconds of spec
# serialization) get heavy well before 50k. A density heatmap is inherently
# approximate, so subsampling this aggressively costs no visible accuracy.
_HEATMAP_MAX_ROWS = 15_000


def _per_pose_classification(dataset, classification: pd.Series | None = None) -> pd.Series:
    """Each pose's dominant class, aligned to the dataset's pose index.

    We use the per-trajectory (not per-pose) most-likely class so every pose
    of a given track is attributed consistently to one class — this avoids
    a single track flickering between classes across its lifetime purely
    from per-frame classifier noise.

    `most_likely_class` costs ~1s on the bundled sample, so callers that
    already have it (e.g. `data.loader.load_classification`, cached once per
    dataset) should pass it in via `classification`, sliced to `dataset`'s
    index if `dataset` is a filtered subset. Falls back to computing it here
    (slower, but keeps this function usable standalone).
    """
    if classification is not None:
        return classification.loc[dataset.index]
    return dataset.most_likely_class(by="trajectory", broadcast=True)


def speed_distribution(dataset, classification: pd.Series | None = None) -> pd.DataFrame:
    """One row per pose. Columns: 'classification' (str), 'speed' (m/s)."""
    classification = _per_pose_classification(dataset, classification)
    speed = dataset[("velocity", "magnitude")]
    return pd.DataFrame(
        {
            "classification": classification.to_numpy(),
            "speed": speed.to_numpy(),
        }
    )


def acceleration_distribution(dataset, classification: pd.Series | None = None) -> pd.DataFrame:
    """One row per pose. Columns: 'classification' (str), 'acceleration' (m/s^2)."""
    classification = _per_pose_classification(dataset, classification)
    acceleration = dataset[("acceleration", "magnitude")]
    return pd.DataFrame(
        {
            "classification": classification.to_numpy(),
            "acceleration": acceleration.to_numpy(),
        }
    )


def dwell_time_by_class(dataset) -> pd.DataFrame:
    """One row per track: 'track_id', 'classification', 'dwell_seconds'.

    dwell_seconds is the time between each track's first and last pose
    (not total moving time — tracks are contiguous in this dataset so this
    is equivalent, but we compute it directly to stay robust to gaps).
    """
    classification = _per_pose_classification(dataset)
    timestamps = dataset.index.get_level_values("timestamp")
    ids = dataset.index.get_level_values("id")

    frame = pd.DataFrame(
        {
            "track_id": ids,
            "classification": classification.to_numpy(),
            "timestamp": timestamps,
        }
    )

    grouped = frame.groupby("track_id", sort=False)
    first = grouped["timestamp"].min()
    last = grouped["timestamp"].max()
    dwell_seconds = (last - first).dt.total_seconds()
    # classification is constant within a track (per-trajectory assignment)
    classification_by_track = grouped["classification"].first()

    out = pd.DataFrame(
        {
            "track_id": dwell_seconds.index,
            "classification": classification_by_track.to_numpy(),
            "dwell_seconds": dwell_seconds.to_numpy(),
        }
    ).reset_index(drop=True)
    return out


def traffic_flow_over_time(dataset, bin_seconds: int = 60) -> pd.DataFrame:
    """Distinct active-track count per time bin.

    Index: 'time_bin' (tz-aware timestamp, left edge of each bin).
    Column: 'count' = number of distinct tracks with at least one pose
    overlapping that bin (a track counts in every bin it spans, not just
    its first bin).
    """
    timestamps = dataset.index.get_level_values("timestamp")
    ids = dataset.index.get_level_values("id")

    track_span = pd.DataFrame({"id": ids, "timestamp": timestamps}).groupby(
        "id", sort=False
    )["timestamp"].agg(["min", "max"])

    session_start = timestamps.min()
    session_end = timestamps.max()

    bin_edges = pd.date_range(
        start=session_start.floor(f"{bin_seconds}s"),
        end=session_end + pd.Timedelta(seconds=bin_seconds),
        freq=f"{bin_seconds}s",
    )

    counts = []
    for bin_start, bin_end in zip(bin_edges[:-1], bin_edges[1:]):
        overlapping = (track_span["min"] < bin_end) & (track_span["max"] >= bin_start)
        counts.append(int(overlapping.sum()))

    out = pd.DataFrame({"time_bin": bin_edges[:-1], "count": counts})
    out = out.set_index("time_bin")
    # Drop trailing empty bins past the last activity, if any.
    out = out[out.index <= session_end]
    return out


def heatmap_points(dataset) -> pd.DataFrame:
    """One row per pose (subsampled if very large). Columns: 'easting', 'northing'."""
    easting = dataset[("position", "easting")].to_numpy()
    northing = dataset[("position", "northing")].to_numpy()
    out = pd.DataFrame({"easting": easting, "northing": northing})

    if len(out) > _HEATMAP_MAX_ROWS:
        rng = np.random.default_rng(seed=0)
        idx = rng.choice(len(out), size=_HEATMAP_MAX_ROWS, replace=False)
        idx.sort()
        out = out.iloc[idx].reset_index(drop=True)

    return out
