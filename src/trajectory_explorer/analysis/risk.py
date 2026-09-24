"""Per-track "current risk level" derived from pairwise interactions.

Integration glue between `analysis.interaction.pairwise_interactions` and the
live risk-coloring feature in the UI: at a given playback timestamp, each
track is assigned the worst (lowest-TTC) risk level among the interactions
it's currently involved in.
"""

from __future__ import annotations

import pandas as pd

# TTC thresholds (seconds) for the 3-level risk scale used by
# `viz.colors.RISK_COLORS`. Below `HIGH_TTC_S` is "high" risk, below
# `MEDIUM_TTC_S` is "medium", otherwise (or no defined TTC) "low".
HIGH_TTC_S = 2.0
MEDIUM_TTC_S = 5.0


def _level_for_ttc(ttc_s: float) -> str:
    if ttc_s < HIGH_TTC_S:
        return "high"
    if ttc_s < MEDIUM_TTC_S:
        return "medium"
    return "low"


def current_risk_by_track(
    interactions: pd.DataFrame,
    timestamp: pd.Timestamp,
    tolerance: pd.Timedelta = pd.Timedelta(milliseconds=100),
) -> dict[int, str]:
    """Risk level ("low"/"medium"/"high") per track id active near `timestamp`.

    Only tracks that appear in `interactions` near this timestamp with a
    defined (non-NaN) `ttc_s` get an entry -- tracks with no nearby,
    currently-closing interaction are simply absent from the returned dict
    (callers should treat that as "no override", i.e. fall back to the
    default class color).
    """
    if interactions.empty:
        return {}

    window = interactions[
        (interactions["timestamp"] >= timestamp - tolerance)
        & (interactions["timestamp"] <= timestamp + tolerance)
    ].dropna(subset=["ttc_s"])

    if window.empty:
        return {}

    best: dict[int, float] = {}
    for _, row in window.iterrows():
        ttc = float(row["ttc_s"])
        for track_id in (int(row["id_a"]), int(row["id_b"])):
            if track_id not in best or ttc < best[track_id]:
                best[track_id] = ttc

    return {track_id: _level_for_ttc(ttc) for track_id, ttc in best.items()}
