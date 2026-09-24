"""Pairwise safety/interaction metrics: TTC and DRAC.

The installed `tasi` (0.15.4) does not ship ready-made TTC/DRAC metrics —
only `tasi.smos.pet.PET` (Post-Encroachment Time, pairwise, requires the two
trajectories' paths to geometrically cross; it raises `RuntimeError`
otherwise, which we treat as "no PET value", not an error). TTC and DRAC are
implemented here from scratch using a standard simplified,
straight-line/constant-velocity model (not bounding-box or heading aware).

Performance approach: rather than a naive double loop over every pair *and*
every timestamp, we group poses by timestamp (frames are small — a couple
dozen tracks active at once for this dataset) and do one vectorized O(n^2)
numpy computation per frame. With ~3600 frames and ~14 tracks/frame on
average for the sample session this runs in low single-digit seconds; see
`if __name__ == "__main__"` / the validation run for the measured wall time.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd

_INTERACTION_COLUMNS = ["timestamp", "id_a", "id_b", "distance_m", "ttc_s", "drac_mps2"]


def pairwise_interactions(
    dataset,
    max_distance_m: float = 15.0,
    progress_callback=None,
) -> pd.DataFrame:
    """Framewise pairwise distance/TTC/DRAC for nearby track pairs.

    For every timestamp and every pair of distinct tracks (id_a < id_b) that
    are both present at that timestamp and within `max_distance_m` of each
    other, computes:

    - distance_m: euclidean distance between positions.
    - ttc_s: time-to-collision under a straight-line, constant-velocity
      assumption. Let rel_pos = pos_b - pos_a, rel_vel = vel_b - vel_a. The
      rate of change of the separation distance is
      d(distance)/dt = (rel_pos . rel_vel) / distance. We define the
      closing speed as the negative of that: closing_speed =
      -(rel_pos . rel_vel) / distance. When closing_speed > 0 (the pair is
      approaching along the line connecting them), ttc_s = distance /
      closing_speed. Otherwise (moving apart or purely tangential motion)
      ttc_s is NaN ("not currently closing").
    - drac_mps2: deceleration-to-avoid-crash, only defined under the same
      closing condition: drac_mps2 = closing_speed^2 / (2 * distance).

    This is the standard simplified TTC/DRAC formulation used e.g. in
    surrogate-safety-measure literature (a straight-line projection of
    relative motion onto the line of sight) — it ignores vehicle heading,
    footprint/bounding-box extent, and any acceleration, so it can
    under/over-estimate risk for large or turning vehicles at close range.

    Returns a long DataFrame with columns: timestamp, id_a, id_b,
    distance_m, ttc_s, drac_mps2. Only pairs within max_distance_m at a
    given timestamp are included (cheap prefilter for tractability).

    `progress_callback`, if given, is called periodically as
    `progress_callback(frames_done, frames_total)` -- e.g. to drive a
    Streamlit progress bar for this ~5-10s computation. Purely cosmetic,
    never changes the result.
    """
    timestamps = dataset.index.get_level_values("timestamp")
    ids = dataset.index.get_level_values("id")

    frame = pd.DataFrame(
        {
            "timestamp": timestamps,
            "id": ids,
            "x": dataset[("position", "easting")].to_numpy(),
            "y": dataset[("position", "northing")].to_numpy(),
            "vx": dataset[("velocity", "easting")].to_numpy(),
            "vy": dataset[("velocity", "northing")].to_numpy(),
        }
    )

    records: list[pd.DataFrame] = []

    groups = frame.groupby("timestamp", sort=False)
    frames_total = groups.ngroups
    progress_every = max(1, frames_total // 100)

    for frame_i, (ts, group) in enumerate(groups):
        if progress_callback is not None and frame_i % progress_every == 0:
            progress_callback(frame_i, frames_total)

        n = len(group)
        if n < 2:
            continue

        # Sort by id so triu index order (ia < ib) also guarantees
        # ids[ia] < ids[ib], avoiding a separate swap step afterwards.
        group = group.sort_values("id")
        gid = group["id"].to_numpy()
        x = group["x"].to_numpy()
        y = group["y"].to_numpy()
        vx = group["vx"].to_numpy()
        vy = group["vy"].to_numpy()

        dx = x[:, None] - x[None, :]
        dy = y[:, None] - y[None, :]
        dist = np.sqrt(dx * dx + dy * dy)

        ia, ib = np.triu_indices(n, k=1)
        d = dist[ia, ib]
        keep = d <= max_distance_m
        if not keep.any():
            continue
        ia, ib, d = ia[keep], ib[keep], d[keep]

        rel_x = x[ib] - x[ia]
        rel_y = y[ib] - y[ia]
        rel_vx = vx[ib] - vx[ia]
        rel_vy = vy[ib] - vy[ia]

        dot = rel_x * rel_vx + rel_y * rel_vy
        closing_speed = -dot / d

        closing = closing_speed > 0
        ttc = np.full(len(d), np.nan)
        drac = np.full(len(d), np.nan)
        ttc[closing] = d[closing] / closing_speed[closing]
        drac[closing] = closing_speed[closing] ** 2 / (2 * d[closing])

        records.append(
            pd.DataFrame(
                {
                    "timestamp": ts,
                    "id_a": gid[ia],
                    "id_b": gid[ib],
                    "distance_m": d,
                    "ttc_s": ttc,
                    "drac_mps2": drac,
                }
            )
        )

    if progress_callback is not None:
        progress_callback(frames_total, frames_total)

    if not records:
        return pd.DataFrame(columns=_INTERACTION_COLUMNS)

    out = pd.concat(records, ignore_index=True)
    return out[_INTERACTION_COLUMNS]


def conflict_ranking(interactions: pd.DataFrame, top_n: int = 20) -> pd.DataFrame:
    """Top-N most severe (id_a, id_b) conflicts.

    Ranked by minimum ttc_s ascending (NaN ttc_s, i.e. "never closing",
    excluded from consideration as a conflict), with maximum drac_mps2 as a
    tiebreaker. Columns: id_a, id_b, min_ttc_s, max_drac_mps2,
    worst_timestamp (timestamp at which min_ttc_s occurred), n_frames
    (number of frames this pair was within max_distance_m).
    """
    columns = [
        "id_a",
        "id_b",
        "min_ttc_s",
        "max_drac_mps2",
        "worst_timestamp",
        "n_frames",
    ]
    if interactions.empty:
        return pd.DataFrame(columns=columns)

    valid = interactions.dropna(subset=["ttc_s"])
    if valid.empty:
        return pd.DataFrame(columns=columns)

    idx_min_ttc = valid.groupby(["id_a", "id_b"])["ttc_s"].idxmin()
    worst = valid.loc[
        idx_min_ttc, ["id_a", "id_b", "ttc_s", "timestamp"]
    ].rename(columns={"ttc_s": "min_ttc_s", "timestamp": "worst_timestamp"})

    max_drac = (
        interactions.groupby(["id_a", "id_b"])["drac_mps2"]
        .max()
        .rename("max_drac_mps2")
    )
    n_frames = interactions.groupby(["id_a", "id_b"]).size().rename("n_frames")

    out = worst.merge(max_drac, on=["id_a", "id_b"]).merge(
        n_frames, on=["id_a", "id_b"]
    )
    out = (
        out.sort_values(["min_ttc_s", "max_drac_mps2"], ascending=[True, False])
        .head(top_n)
        .reset_index(drop=True)
    )
    return out[columns]


def near_miss_count(interactions: pd.DataFrame, ttc_threshold_s: float = 1.5) -> int:
    """Count of distinct (id_a, id_b) pairs whose min ttc_s < ttc_threshold_s."""
    if interactions.empty:
        return 0
    valid = interactions.dropna(subset=["ttc_s"])
    if valid.empty:
        return 0
    min_ttc = valid.groupby(["id_a", "id_b"])["ttc_s"].min()
    return int((min_ttc < ttc_threshold_s).sum())


def pet_for_pair(dataset, id_a: int, id_b: int) -> float | None:
    """Post-Encroachment Time (seconds) for a pair of tracks, or None.

    Thin wrapper around `tasi.smos.pet.PET.estimate`. Returns None when the
    two trajectories' paths never geometrically cross (that estimator
    raises RuntimeError in this case — treated here as "no PET value", not
    a failure) or when either track is missing from the dataset.
    """
    from tasi.smos.pet import PET

    try:
        ego = dataset.trajectory(id_a)
        challenger = dataset.trajectory(id_b)
    except KeyError:
        return None

    try:
        result = PET.estimate(ego, challenger)
    except RuntimeError:
        return None

    if result is None:
        return None
    # `estimate` may return a scalar or a small series/array of PET values
    # (return_first defaults to True, so a scalar is the common case).
    if isinstance(result, (int, float, np.floating)):
        return float(result)
    try:
        return float(result.iloc[0]) if hasattr(result, "iloc") else float(result[0])
    except (TypeError, IndexError):
        return float(result)


if __name__ == "__main__":
    from trajectory_explorer.data.loader import load_dataset

    ds = load_dataset("dlr_ut_session_01")
    t0 = time.perf_counter()
    interactions = pairwise_interactions(ds)
    elapsed = time.perf_counter() - t0
    print(f"pairwise_interactions: {elapsed:.2f}s, {len(interactions)} rows")
    print(interactions.head())

    ranking = conflict_ranking(interactions)
    print(ranking.head())
    print("near misses (<1.5s):", near_miss_count(interactions))
