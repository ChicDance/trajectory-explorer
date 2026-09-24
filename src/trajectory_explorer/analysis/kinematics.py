"""Per-object kinematic time series.

Thin extraction layer on top of a `tasi.dlr.DLRTrajectoryDataset`: pulls the
velocity/acceleration/yaw columns for a single track and reshapes them into
the flat, timestamp-indexed frame the `viz.charts` module expects.
"""

from __future__ import annotations

import pandas as pd


def object_timeseries(dataset, track_id: int) -> pd.DataFrame:
    """Return kinematics for one track, indexed by timestamp.

    Columns: 'speed' (m/s, from velocity.magnitude), 'acceleration'
    (m/s^2, from acceleration.magnitude), 'heading' (degrees, from yaw).
    Sorted by timestamp ascending.
    """
    traj = dataset.trajectory(track_id)

    out = pd.DataFrame(
        {
            "speed": traj[("velocity", "magnitude")].to_numpy(),
            "acceleration": traj[("acceleration", "magnitude")].to_numpy(),
            "heading": traj[("yaw", "")].to_numpy(),
        },
        index=traj.index.get_level_values("timestamp"),
    )
    out.index.name = "timestamp"
    out = out.sort_index()
    return out
