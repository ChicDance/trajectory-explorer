"""One-off script: cut a small, git-trackable sample (a few minutes, a few
hundred trajectories) from an already-downloaded DLR-UT recording for the
bundled demo.

Keeps the original flat DLR-UT CSV layout (timestamp, id, center_easting, ...)
so the sample can be loaded with the exact same `DLRTrajectoryDataset.from_csv`
code path as a full recording.

Run scripts/download_dlr_ut.py first to populate data_cache/ (gitignored,
~460MB, not meant to be committed).

Usage: uv run python scripts/fetch_sample_data.py
"""

from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT / "data_cache"
SAMPLE_DIR = ROOT / "sample_data" / "dlr_ut"

# a moderately busy 15-minute recording (09:00-09:15, weekday morning) with a
# good mix of object classes (cars, bicycles, pedestrians, trucks, ...)
SOURCE_FILE = (
    CACHE_DIR
    / "DLR-Urban-Traffic-dataset_v1-3-1"
    / "raw_data"
    / "trajectories"
    / "trajectories_230924-090000_230924-091500.csv"
)

SAMPLE_SECONDS = 180


def main() -> None:
    SAMPLE_DIR.mkdir(parents=True, exist_ok=True)

    print(f"Reading {SOURCE_FILE.name} ...")
    raw = pd.read_csv(SOURCE_FILE, parse_dates=["timestamp"])
    print(f"Full recording: {len(raw)} rows, {raw['id'].nunique()} tracks")

    start = raw["timestamp"].min()
    cutoff = start + pd.Timedelta(seconds=SAMPLE_SECONDS)

    sample = raw[raw["timestamp"] <= cutoff].copy()
    print(f"Sample window: {start} .. {cutoff} -> {len(sample)} rows, "
          f"{sample['id'].nunique()} tracks")

    out_path = SAMPLE_DIR / "session_01.csv"
    sample.to_csv(out_path, index=False)
    print(f"\nWrote sample to {out_path} ({out_path.stat().st_size / 1e6:.2f} MB)")

    # verify round-trip through the exact loader the app will use
    from tasi.dlr import DLRTrajectoryDataset

    reloaded = DLRTrajectoryDataset.from_csv(str(out_path))
    print("\nVerification (reload via DLRTrajectoryDataset.from_csv):")
    print(f"  rows={len(reloaded)}, tracks={reloaded.index.get_level_values('id').nunique()}")
    print(reloaded.most_likely_class(by="trajectory").value_counts())


if __name__ == "__main__":
    main()
